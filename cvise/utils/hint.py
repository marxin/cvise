"""Helpers for working with "hints" - descriptions of edits to be attempted.

A hint is a compact JSON object that describes one or multiple modifications of
the input: deletion of text at a particular location, replacement with new
text, etc.

The usage of hints, as a protocol, allows to simplify implementing reduction
heuristics and to perform reduction more efficiently (as algorithms can now be
applied to all heuristics in a uniform way).
"""

from copy import copy, deepcopy
from dataclasses import dataclass, field
import json
from pathlib import Path
from typing import Any, Dict, List, Sequence, TextIO, Tuple
import zstandard


# Currently just a hardcoded constant - the number is reserved for backwards-incompatible format changes in the future.
FORMAT_NAME = 'cvise_hints_v0'


@dataclass
class HintBundle:
    """Stores a collection of hints.

    Its standard serialization format is a newline-separated JSON of the following structure:

      <Preamble object>\n
      <Vocabulary array>\n
      <Hint 1 object>\n
      <Hint 2 object>\n
      ...
    """

    # Hint objects - each item matches the `HINT_SCHEMA`.
    hints: List[object]
    pass_name: str = ''
    # Strings that hints can refer to.
    # Note: a simple "= []" wouldn't be suitable because mutable default values are error-prone in Python.
    vocabulary: List[str] = field(default_factory=list)


# JSON Schemas:

HINT_PATCH_SCHEMA = {
    'description': 'Hint patch object. By default, unless a specific property is specified, the object denotes a simple deletion of the specified chunk.',
    'type': 'object',
    'properties': {
        'l': {
            'description': 'Left position of the chunk (position is an index of the character in the text)',
            'type': 'integer',
            'minimum': 0,
        },
        'r': {
            'description': "Right position of the chunk (index of the next character in the text after the chunk's last character). Must be greater than 'l'.",
            'type': 'integer',
        },
        'v': {
            'description': 'Indicates that the chunk needs to be replaced with a new value - the string with the specified index in the vocabulary.',
            'type': 'integer',
            'minimum': 0,
        },
    },
    'required': ['l', 'r'],
}

HINT_PATCH_SCHEMA_STRICT = deepcopy(HINT_PATCH_SCHEMA)
HINT_PATCH_SCHEMA_STRICT['additionalProperties'] = False

HINT_SCHEMA = {
    'description': 'Hint object - a description of modification(s) of the input',
    'type': 'object',
    'properties': {
        'p': {
            'description': 'Patches that this hint consists of',
            'type': 'array',
            'items': HINT_PATCH_SCHEMA,
            'minItems': 1,
        },
        't': {
            'description': (
                'Indicates the type of the hint, as an index in the vocabulary. The purpose of the type is to let a '
                'pass split hints into distinct groups, to guide the generic logic that attempts taking consecutive '
                'ranges of same-typed hints.'
            ),
            'type': 'integer',
            'minimum': 0,
        },
    },
    'required': ['p'],
}

HINT_SCHEMA_STRICT = deepcopy(HINT_SCHEMA)
HINT_SCHEMA_STRICT['additionalProperties'] = False
HINT_SCHEMA_STRICT['properties']['p']['items'] = HINT_PATCH_SCHEMA_STRICT


@dataclass
class HintApplicationStats:
    size_delta_per_pass: Dict[str, int]

    def get_passes_ordered_by_delta(self) -> List[str]:
        ordered = sorted(self.size_delta_per_pass.items(), key=lambda kv: kv[1])
        return [kv[0] for kv in ordered]


def apply_hints(bundles: List[HintBundle], file: Path) -> Tuple[bytes, HintApplicationStats]:
    """Edits the file applying the specified hints to its contents."""
    patches = []
    for bundle in bundles:
        for hint in bundle.hints:
            for patch in hint['p']:
                p = copy(patch)
                p['_bundle'] = bundle
                patches.append(p)
    merged_patches = merge_overlapping_patches(patches)

    with open(file, 'rb') as f:
        orig_data = f.read()

    new_data = b''
    stats = HintApplicationStats(size_delta_per_pass={})
    start_pos = 0
    for p in merged_patches:
        left: int = p['l']
        right: int = p['r']
        bundle: HintBundle = p['_bundle']
        assert start_pos <= left < len(orig_data)
        assert left < right <= len(orig_data)
        # Add the unmodified chunk up to the current patch begin.
        new_data += orig_data[start_pos:left]
        # Skip the original chunk inside the current patch.
        start_pos = right
        stats.size_delta_per_pass.setdefault(bundle.pass_name, 0)
        stats.size_delta_per_pass[bundle.pass_name] -= right - left
        # Insert the replacement value, if provided.
        if 'v' in p:
            to_insert = bundle.vocabulary[p['v']].encode()
            new_data += to_insert
            stats.size_delta_per_pass[bundle.pass_name] += len(to_insert)
    # Add the unmodified chunk after the last patch end.
    new_data += orig_data[start_pos:]
    return new_data, stats


def store_hints(bundle: HintBundle, hints_file_path: Path) -> None:
    """Serializes hints to the given file.

    We currently use the Zstandard compression to reduce the space usage (the empirical compression ratio observed for
    hint JSONs is around 5x..20x)."""
    with zstandard.open(hints_file_path, 'wt') as f:
        write_compact_json(make_preamble(bundle), f)
        f.write('\n')
        write_compact_json(bundle.vocabulary, f)
        f.write('\n')
        for h in bundle.hints:
            write_compact_json(h, f)
            f.write('\n')


def load_hints(hints_file_path: Path, begin_index: int, end_index: int) -> HintBundle:
    """Deserializes hints with the given indices [begin; end) from a file.

    Whether the hints file is compressed is determined based on the file extension."""
    assert begin_index < end_index
    bundle = HintBundle(hints=[])
    with zstandard.open(hints_file_path, 'rt') if hints_file_path.suffix == '.zst' else open(hints_file_path) as f:
        parse_preamble(try_parse_json_line(next(f)), bundle)

        vocab = try_parse_json_line(next(f))
        # Do a lightweight check that'd catch a basic mistake (a hint object coming instead of a vocabulary array). We
        # don't want to perform full type/schema checking during loading due to performance concerns.
        if not isinstance(vocab, list):
            raise RuntimeError(f'Failed to read hint vocabulary: expected array, instead got: {vocab}')
        bundle.vocabulary = vocab

        for i, line in enumerate(f):
            if begin_index <= i < end_index:
                bundle.hints.append(try_parse_json_line(line))
    return bundle


def group_hints_by_type(bundle: HintBundle) -> Dict[str, HintBundle]:
    """Splits the bundle into multiple, one per each hint type."""
    grouped: Dict[str, HintBundle] = {}
    for h in bundle.hints:
        type = bundle.vocabulary[h['t']] if 't' in h else ''
        if type not in grouped:
            grouped[type] = HintBundle(vocabulary=bundle.vocabulary, hints=[], pass_name=bundle.pass_name)
        # FIXME: drop the 't' property in favor of storing it once, in the bundle's preamble
        grouped[type].hints.append(h)
    return grouped


def make_preamble(bundle: HintBundle) -> Dict[str, Any]:
    preamble = {
        'format': FORMAT_NAME,
    }
    if bundle.pass_name:
        preamble['pass'] = bundle.pass_name
    return preamble


def parse_preamble(json: Any, bundle: HintBundle) -> None:
    if not isinstance(json, dict):
        raise RuntimeError(f'Failed to parse hint bundle preamble: expected object, instead got {json}')
    format = json.get('format')
    if format != FORMAT_NAME:
        raise RuntimeError(
            f'Failed to parse hint bundle preamble: expected format "{FORMAT_NAME}", instead got {repr(format)}'
        )

    if 'pass' in json:
        bundle.pass_name = json['pass']


def write_compact_json(value: Any, file: TextIO) -> None:
    """Writes a JSON dump, as a compact representation (without unnecessary spaces), to the file.

    Skips circular structure checks, for performance reasons."""
    # Specify custom separators - the default ones have spaces after them.
    json.dump(value, file, check_circular=False, separators=(',', ':'))


def try_parse_json_line(text: str) -> Any:
    try:
        return json.loads(text)
    except json.decoder.JSONDecodeError as e:
        raise RuntimeError(f'Failed to decode line "{text}": {e}') from e


def merge_overlapping_patches(patches: Sequence[object]) -> Sequence[object]:
    """Returns non-overlapping hint patches, merging patches where necessary."""

    def sorting_key(patch):
        is_replacement = 'v' in patch
        # Among all patches starting in the same location, use additional criteria:
        # * prefer seeing larger patches first, hence sort by decreasing "r";
        # * (if still a tie) prefer deletion over text replacement.
        return patch['l'], -patch['r'], is_replacement

    merged = []
    for patch in sorted(patches, key=sorting_key):
        if merged and patches_overlap(merged[-1], patch):
            extend_end_to_fit(merged[-1], patch)
        else:
            merged.append(patch)
    return merged


def patches_overlap(first: object, second: object) -> bool:
    """Checks whether two patches overlap.

    Only real overlaps (with at least one common character) are counted - False
    is returned for patches merely touching each other.
    """
    return max(first['l'], second['l']) < min(first['r'], second['r'])


def extend_end_to_fit(patch: object, appended_patch: object) -> None:
    """Modifies the first patch so that the second patch fits into it."""
    patch['r'] = max(patch['r'], appended_patch['r'])

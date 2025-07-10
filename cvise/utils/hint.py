"""Helpers for working with "hints" - descriptions of edits to be attempted.

A hint is a compact JSON object that describes one or multiple modifications of
the input: deletion of text at a particular location, replacement with new
text, etc.

The usage of hints, as a protocol, allows to simplify implementing reduction
heuristics and to perform reduction more efficiently (as algorithms can now be
applied to all heuristics in a uniform way).
"""

from dataclasses import dataclass, field
import json
from pathlib import Path
from typing import Any, Dict, List, Sequence, TextIO
import zstandard


@dataclass
class HintBundle:
    """Stores a collection of hints.

    Its standard serialization format is a newline-separated JSON of the following structure:

      <Vocabulary array>\n
      <Hint 1 object>\n
      <Hint 2 object>\n
      ...
    """

    # Hint objects - each item matches the `HINT_SCHEMA`.
    hints: List[object]
    # Strings that hints can refer to.
    # Note: a simple "= []" wouldn't be suitable because mutable default values are error-prone in Python.
    vocabulary: List[str] = field(default_factory=list)


# JSON Schemas:

HINT_PATCH_SCHEMA = {
    'description': 'Hint patch object. By default, unless a specific property is specified, the object denotes a simple deletion of the specified chunk.',
    'type': 'object',
    'properties': {
        't': {
            'description': (
                'Indicates the type of the hint, as an index in the vocabulary. The purpose of the type is to let a '
                'pass split hints into distinct groups, to guide the generic logic that attempts taking consecutive '
                'ranges of same-typed hints.'
            ),
            'type': 'integer',
            'minimum': 0,
        },
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
    },
    'required': ['p'],
}


def apply_hints(bundle: HintBundle, file: Path) -> str:
    """Edits the file applying the specified hints to its contents."""
    patches = sum((h['p'] for h in bundle.hints), start=[])
    merged_patches = merge_overlapping_patches(patches)

    with open(file) as f:
        orig_data = f.read()

    new_data = ''
    start_pos = 0
    for p in merged_patches:
        left = p['l']
        right = p['r']
        assert start_pos <= left < len(orig_data)
        assert left < right <= len(orig_data)
        # Add the unmodified chunk up to the current patch begin.
        new_data += orig_data[start_pos:left]
        # Skip the original chunk inside the current patch.
        start_pos = right
        # Insert the replacement value, if provided.
        if 'v' in p:
            new_data += bundle.vocabulary[p['v']]
    # Add the unmodified chunk after the last patch end.
    new_data += orig_data[start_pos:]
    return new_data


def store_hints(bundle: HintBundle, hints_file_path: Path) -> None:
    """Serializes hints to the given file.

    We currently use the Zstandard compression to reduce the space usage (the empirical compression ratio observed for
    hint JSONs is around 5x..20x)."""
    with zstandard.open(hints_file_path, 'wt') as f:
        write_compact_json(bundle.vocabulary, f)
        f.write('\n')
        for h in bundle.hints:
            write_compact_json(h, f)
            f.write('\n')


def load_hints(hints_file_path: Path, begin_index: int, end_index: int) -> HintBundle:
    """Deserializes hints with the given indices [begin; end) from a file.

    Whether the hints file is compressed is determined based on the file extension."""
    assert begin_index < end_index
    hints = []
    with zstandard.open(hints_file_path, 'rt') if hints_file_path.suffix == '.zst' else open(hints_file_path) as f:
        vocab = try_parse_json_line(next(f))
        # Do a lightweight check that'd catch a basic mistake (a hint object coming instead of a vocabulary array). We
        # don't want to perform full type/schema checking during loading due to performance concerns.
        if not isinstance(vocab, list):
            raise RuntimeError(f'Failed to read hint vocabulary: expected array, instead got: {vocab}')

        for i, line in enumerate(f):
            if begin_index <= i < end_index:
                hints.append(try_parse_json_line(line))
    return HintBundle(hints=hints, vocabulary=vocab)


def group_hints_by_type(bundle: HintBundle) -> Dict[str, HintBundle]:
    """Splits the bundle into multiple, one per each hint type."""
    grouped: Dict[str, HintBundle] = {}
    for h in bundle.hints:
        type = bundle.vocabulary[h['t']] if 't' in h else ''
        if type not in grouped:
            grouped[type] = HintBundle(vocabulary=bundle.vocabulary, hints=[])
        # FIXME: drop the 't' property in favor of storing it once, in the bundle's preamble
        grouped[type].hints.append(h)
    return grouped


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
        # Among all patches starting in the same location, deletion should take precedence over text replacement.
        return patch['l'], is_replacement

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

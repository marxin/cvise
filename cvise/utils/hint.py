"""Helpers for working with "hints" - descriptions of edits to be attempted.

A hint is a compact JSON object that describes one or multiple modifications of
the input: deletion of text at a particular location, replacement with new
text, etc.

The usage of hints, as a protocol, allows to simplify implementing reduction
heuristics and to perform reduction more efficiently (as algorithms can now be
applied to all heuristics in a uniform way).
"""

from copy import deepcopy
from dataclasses import dataclass, field
import json
import msgspec
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, TextIO, Union
import zstandard

from cvise.utils.fileutil import mkdir_up_to


# Currently just a hardcoded constant - the number is reserved for backwards-incompatible format changes in the future.
FORMAT_NAME = 'cvise_hints_v0'


class Patch(msgspec.Struct, kw_only=True, omit_defaults=True):
    left: int = msgspec.field(name='l')
    right: int = msgspec.field(name='r')
    file: Optional[int] = msgspec.field(default=None, name='f')
    value: Optional[int] = msgspec.field(default=None, name='v')


class Hint(msgspec.Struct, omit_defaults=True):
    patches: List[Patch] = msgspec.field(name='p')
    type: Optional[int] = msgspec.field(default=None, name='t')


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
    hints: List[Hint]
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
        'f': {
            'description': 'Specifies file where the patch is to be applied - the path is the string with the specified index in the vocabulary. Must be specified iff the input is a directory.',
            'type': 'integer',
            'minimum': 0,
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
                'Indicates the type of the hint, as an index in the vocabulary. Types starting from "@" (the at sign) '
                'have special meaning - such hints are not attempted as reduction transformations, but are only '
                'intended to be consumed by other passes as input data. Types not starting from "@" are just used as a '
                'way to split hints from a particular pass into distinct groups, to guide the generic logic that '
                'attempts taking consecutive ranges of same-typed hints.'
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


# A singleton encoder object, to save time on recreating it.
json_encoder: Union[msgspec.json.Encoder, None] = None


def is_special_hint_type(type: str) -> bool:
    return type.startswith('@')


class _PatchWithBundleRef(Patch):
    bundle: HintBundle


def apply_hints(bundles: List[HintBundle], source_path: Path, destination_path: Path) -> HintApplicationStats:
    """Creates the destination file/dir by applying the specified hints to the contents of the source file/dir."""
    # Take patches from all hints and group them by the file which they're applied to.
    path_to_patches = {}
    for bundle in bundles:
        for hint in bundle.hints:
            for patch in hint.patches:
                p = _PatchWithBundleRef(
                    left=patch.left, right=patch.right, file=patch.file, value=patch.value, bundle=bundle
                )
                file_rel = Path(bundle.vocabulary[patch.file]) if patch.file is not None else Path()
                path_to_patches.setdefault(file_rel, []).append(p)

    # Enumerate all files in the source location and apply corresponding patches, if any, to each.
    is_dir = source_path.is_dir()
    subtree = list(source_path.rglob('*')) if is_dir else [source_path]
    stats = HintApplicationStats(size_delta_per_pass={})
    for path in subtree:
        if path.is_dir() or path.is_symlink():
            continue

        file_rel = path.relative_to(source_path)
        file_dest = destination_path / file_rel
        if is_dir:
            mkdir_up_to(file_dest.parent, destination_path.parent)

        patches_to_apply = path_to_patches.get(file_rel, [])
        apply_hint_patches_to_file(patches_to_apply, source_file=path, destination_file=file_dest, stats=stats)

    return stats


def apply_hint_patches_to_file(
    patches: List[_PatchWithBundleRef], source_file: Path, destination_file: Path, stats: HintApplicationStats
) -> None:
    merged_patches = merge_overlapping_patches(patches)
    orig_data = source_file.read_bytes()

    new_data = b''
    start_pos = 0
    for p in merged_patches:
        bundle: HintBundle = p.bundle
        assert start_pos <= p.left < len(orig_data)
        assert p.left < p.right <= len(orig_data)
        # Add the unmodified chunk up to the current patch begin.
        new_data += orig_data[start_pos : p.left]
        # Skip the original chunk inside the current patch.
        start_pos = p.right
        stats.size_delta_per_pass.setdefault(bundle.pass_name, 0)
        stats.size_delta_per_pass[bundle.pass_name] -= p.right - p.left
        # Insert the replacement value, if provided.
        if p.value is not None:
            to_insert = bundle.vocabulary[p.value].encode()
            new_data += to_insert
            stats.size_delta_per_pass[bundle.pass_name] += len(to_insert)
    # Add the unmodified chunk after the last patch end.
    new_data += orig_data[start_pos:]

    destination_file.write_bytes(new_data)


def store_hints(bundle: HintBundle, hints_file_path: Path) -> None:
    """Serializes hints to the given file.

    We currently use the Zstandard compression to reduce the space usage (the empirical compression ratio observed for
    hint JSONs is around 5x..20x).
    """

    # Use chunks of this or greater size when calling into Zstandard.
    WRITE_BUFFER = 2**18

    global json_encoder
    if json_encoder is None:
        json_encoder = msgspec.json.Encoder()

    with zstandard.open(hints_file_path, 'wb') as f:
        buf = bytearray()

        # "offset=-1" means appending ot the end of the buf
        json_encoder.encode_into(make_preamble(bundle), buf, -1)
        buf.append(ord('\n'))

        json_encoder.encode_into(bundle.vocabulary, buf, -1)
        buf.append(ord('\n'))

        for h in bundle.hints:
            if len(buf) > WRITE_BUFFER:
                f.write(buf)
                buf.clear()
            json_encoder.encode_into(h, buf, -1)
            buf.append(ord('\n'))
        f.write(buf)


def load_hints(hints_file_path: Path, begin_index: Union[int, None], end_index: Union[int, None]) -> HintBundle:
    """Deserializes hints from a file.

    If provided, the [begin; end) half-range can be used to only load hints with the specified indices.

    Whether the hints file is compressed is determined based on the file extension."""
    if begin_index is not None and end_index is not None:
        assert begin_index < end_index
    bundle = HintBundle(hints=[])
    with zstandard.open(hints_file_path, 'rt') if hints_file_path.suffix == '.zst' else open(hints_file_path) as f:
        decoder = msgspec.json.Decoder()
        parse_preamble(try_parse_json_line(next(f), decoder), bundle)

        vocab = try_parse_json_line(next(f), decoder)
        # Do a lightweight check that'd catch a basic mistake (a hint object coming instead of a vocabulary array). We
        # don't want to perform full type/schema checking during loading due to performance concerns.
        if not isinstance(vocab, list):
            raise RuntimeError(f'Failed to read hint vocabulary: expected array, instead got: {vocab}')
        bundle.vocabulary = vocab

        hint_decoder = msgspec.json.Decoder(type=Hint)
        for i, line in enumerate(f):
            if begin_index is not None and i < begin_index:
                continue
            if end_index is not None and i >= end_index:
                continue
            bundle.hints.append(try_parse_json_line(line, hint_decoder))
    return bundle


def group_hints_by_type(bundle: HintBundle) -> Dict[str, HintBundle]:
    """Splits the bundle into multiple, one per each hint type."""
    grouped: Dict[str, HintBundle] = {}
    for h in bundle.hints:
        type = bundle.vocabulary[h.type] if h.type is not None else ''
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


def try_parse_json_line(text: str, decoder) -> Any:
    try:
        return decoder.decode(text)
    except msgspec.MsgspecError as e:
        raise RuntimeError(f'Failed to decode line "{text}": {e}') from e


def merge_overlapping_patches(patches: Sequence[Patch]) -> Sequence[Patch]:
    """Returns non-overlapping hint patches, merging patches where necessary."""

    def sorting_key(patch):
        is_replacement = patch.value is not None
        # Among all patches starting in the same location, use additional criteria:
        # * prefer seeing larger patches first, hence sort by decreasing "r";
        # * (if still a tie) prefer deletion over text replacement.
        return patch.left, -patch.right, is_replacement

    merged = []
    for patch in sorted(patches, key=sorting_key):
        if merged and patches_overlap(merged[-1], patch):
            extend_end_to_fit(merged[-1], patch)
        else:
            merged.append(patch)
    return merged


def patches_overlap(first: Patch, second: Patch) -> bool:
    """Checks whether two patches overlap.

    Only real overlaps (with at least one common character) are counted - False
    is returned for patches merely touching each other.
    """
    return max(first.left, second.left) < min(first.right, second.right)


def extend_end_to_fit(patch: Patch, appended_patch: Patch) -> None:
    """Modifies the first patch so that the second patch fits into it."""
    patch.right = max(patch.right, appended_patch.right)


def _mkdir_up_to(dir_to_create: Path, last_parent_dir: Path) -> None:
    """Similar to Path.mkdir(parents=True), but stops at the given ancestor directory.

    We use it to avoid canceled-but-not-killed-yet C-Vise jobs recreating temporary work directories that the C-Vise
    main process has deleted.
    """
    assert dir_to_create.is_relative_to(last_parent_dir)
    if dir_to_create != last_parent_dir:
        _mkdir_up_to(dir_to_create.parent, last_parent_dir)
    dir_to_create.mkdir(exist_ok=True)

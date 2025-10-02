"""Helpers for working with "hints" - descriptions of edits to be attempted.

A hint is a compact JSON object that describes one or multiple modifications of
the input: deletion of text at a particular location, replacement with new
text, etc.

The usage of hints, as a protocol, allows to simplify implementing reduction
heuristics and to perform reduction more efficiently (as algorithms can now be
applied to all heuristics in a uniform way).
"""

from copy import deepcopy
import dataclasses
import json
import msgspec
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, TextIO, Tuple
import zstandard

from cvise.utils.fileutil import mkdir_up_to


# Currently just a hardcoded constant - the number is reserved for backwards-incompatible format changes in the future.
FORMAT_NAME = 'cvise_hints_v0'


class Patch(msgspec.Struct, omit_defaults=True, gc=False, frozen=True, order=True, kw_only=True):
    """Describes a single patch inside a hint.

    See HINT_PATCH_SCHEMA.
    """

    file: Optional[int] = msgspec.field(default=None, name='f')
    left: int = msgspec.field(name='l')
    right: int = msgspec.field(name='r')
    operation: Optional[int] = msgspec.field(default=None, name='o')
    value: Optional[int] = msgspec.field(default=None, name='v')


class Hint(msgspec.Struct, omit_defaults=True, gc=False, frozen=True, order=True, kw_only=True):
    """Describes a single hint.

    See HINT_SCHEMA.
    """

    type: Optional[int] = msgspec.field(default=None, name='t')
    patches: Tuple[Patch, ...] = msgspec.field(name='p')
    extra: Optional[int] = msgspec.field(default=None, name='e')


@dataclasses.dataclass
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
    vocabulary: List[bytes] = dataclasses.field(default_factory=list)


# JSON Schemas:

HINT_PATCH_SCHEMA = {
    'description': (
        'Hint patch object. By default, unless a specific property is specified, the object denotes a simple deletion '
        'of the specified chunk.'
    ),
    'type': 'object',
    'properties': {
        'l': {
            'description': 'Left position of the chunk (position is an index of the character in the text)',
            'type': 'integer',
            'minimum': 0,
        },
        'r': {
            'description': (
                "Right position of the chunk (index of the next character in the text after the chunk's last '"
                "'character). Must be greater than 'l'."
            ),
            'type': 'integer',
        },
        'f': {
            'description': (
                'Specifies file where the patch is to be applied - the path is the string with the specified index in '
                'the vocabulary. Must be specified iff the input is a directory.'
            ),
            'type': 'integer',
            'minimum': 0,
        },
        'o': {
            'description': (
                'Specifies the type of the special operation to be performed on the file/chunk. The number specifies '
                'the index in the vocabulary. The only currently supported operation is "rm" - deleting the file.'
            ),
            'type': 'integer',
            'minimum': 0,
        },
        'v': {
            'description': (
                'Indicates that the chunk needs to be replaced with a new value - the string with the specified index '
                'in the vocabulary.'
            ),
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
            'description': 'Patches that this hint consists of. Must be nonempty, except for special hint types.',
            'type': 'array',
            'items': HINT_PATCH_SCHEMA,
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
        'e': {
            'description': (
                'Extra value associated with the hint, as an index in the vocabulary. For example, for "@fileref" '
                'hints this contains the path of the mentioned file.'
            ),
            'type': 'integer',
            'minimum': 0,
        },
    },
}

HINT_SCHEMA_STRICT = deepcopy(HINT_SCHEMA)
HINT_SCHEMA_STRICT['additionalProperties'] = False
HINT_SCHEMA_STRICT['properties']['p']['items'] = HINT_PATCH_SCHEMA_STRICT


@dataclasses.dataclass
class HintApplicationStats:
    size_delta_per_pass: Dict[str, int]

    def get_passes_ordered_by_delta(self) -> List[str]:
        ordered = sorted(self.size_delta_per_pass.items(), key=lambda kv: kv[1])
        return [kv[0] for kv in ordered]


class _BundlePreamble(msgspec.Struct, omit_defaults=True):
    format: str  # the FORMAT_NAME default is not set here, to avoid being omitted by msgspec serialization
    pass_: str = msgspec.field(default='', name='pass')


# Singleton encoder/decoder objects, to save time on recreating them.
_json_encoder: Optional[msgspec.json.Encoder] = None
_encoding_buf: Optional[bytearray] = None
_preamble_decoder: Optional[msgspec.json.Encoder] = None
_vocab_decoder: Optional[msgspec.json.Encoder] = None
_hint_decoder: Optional[msgspec.json.Encoder] = None


def is_special_hint_type(type: bytes) -> bool:
    return type.startswith(b'@')


class _PatchWithBundleRef(msgspec.Struct, gc=False):
    patch: Patch
    bundle_id: int


def apply_hints(bundles: List[HintBundle], source_path: Path, destination_path: Path) -> HintApplicationStats:
    """Creates the destination file/dir by applying the specified hints to the contents of the source file/dir."""
    # Take patches from all hints and group them by the file which they're applied to.
    path_to_patches: Dict[Path, List[_PatchWithBundleRef]] = {}
    for bundle_id, bundle in enumerate(bundles):
        for hint in bundle.hints:
            for patch in hint.patches:
                # Copying sub-structs improves data locality, helping performance in practice.
                p = _PatchWithBundleRef(patch.__copy__(), bundle_id)
                file_rel = Path(bundle.vocabulary[patch.file].decode()) if patch.file is not None else Path()
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
        _apply_hint_patches_to_file(
            patches_to_apply, bundles, source_file=path, destination_file=file_dest, stats=stats
        )

    return stats


def _apply_hint_patches_to_file(
    patches: List[_PatchWithBundleRef],
    bundles: List[HintBundle],
    source_file: Path,
    destination_file: Path,
    stats: HintApplicationStats,
) -> None:
    merged_patches = _merge_overlapping_patches(patches)
    orig_data = memoryview(source_file.read_bytes())

    new_data = bytearray()
    should_rm = False
    start_pos = 0
    for patch_ref in merged_patches:
        p: Patch = patch_ref.patch
        bundle: HintBundle = bundles[patch_ref.bundle_id]
        assert start_pos <= p.left <= len(orig_data)
        assert p.left <= p.right <= len(orig_data)
        if p.operation is not None and bundle.vocabulary[p.operation] == b'rm':
            should_rm = True
        # Add the unmodified chunk up to the current patch begin.
        new_data.extend(orig_data[start_pos : p.left])
        # Skip the original chunk inside the current patch.
        start_pos = p.right
        stats.size_delta_per_pass.setdefault(bundle.pass_name, 0)
        stats.size_delta_per_pass[bundle.pass_name] -= p.right - p.left
        # Insert the replacement value, if provided.
        if p.value is not None:
            to_insert = bundle.vocabulary[p.value]
            new_data += to_insert
            stats.size_delta_per_pass[bundle.pass_name] += len(to_insert)
    # Add the unmodified chunk after the last patch end.
    new_data.extend(orig_data[start_pos:])

    if not should_rm:  # otherwise don't create the file - this is equvalent to removing it
        destination_file.write_bytes(new_data)


def store_hints(bundle: HintBundle, hints_file_path: Path) -> None:
    """Serializes hints to the given file.

    We currently use the Zstandard compression to reduce the space usage (the empirical compression ratio observed for
    hint JSONs is around 5x..20x).
    """

    # Use chunks of this or greater size when calling into Zstandard.
    WRITE_BUFFER = 2**18

    global _json_encoder, _encoding_buf
    if _json_encoder is None:  # lazily initialize singletons
        _json_encoder = msgspec.json.Encoder()
        _encoding_buf = bytearray()
    encoder = _json_encoder  # cache in local variables, which are presumably faster
    buf = _encoding_buf

    with zstandard.open(hints_file_path, 'wb') as f:
        # leave "offset" at default, to make sure the buffer is cleared
        encoder.encode_into(make_preamble(bundle), buf)
        newline = ord('\n')
        buf.append(newline)

        # "offset=-1" means appending to the end of the buf
        encoder.encode_into([s.decode() for s in bundle.vocabulary], buf, -1)
        buf.append(newline)

        for h in bundle.hints:
            if len(buf) <= WRITE_BUFFER:
                offset = -1  # append to the end of the buf
            else:
                f.write(buf)
                offset = 0  # clear the buf
            encoder.encode_into(h, buf, offset)
            buf.append(newline)
        f.write(buf)


def load_hints(hints_file_path: Path, begin_index: Optional[int], end_index: Optional[int]) -> HintBundle:
    """Deserializes hints from a file.

    If provided, the [begin; end) half-range can be used to only load hints with the specified indices.

    Whether the hints file is compressed is determined based on the file extension."""
    if begin_index is not None and end_index is not None:
        assert begin_index < end_index

    global _preamble_decoder, _vocab_decoder, _hint_decoder
    if _preamble_decoder is None:  # lazily initialize singletons
        _preamble_decoder = msgspec.json.Decoder(type=_BundlePreamble)
        _vocab_decoder = msgspec.json.Decoder(type=List[str])
        _hint_decoder = msgspec.json.Decoder(type=Hint)
    preamble_decoder = _preamble_decoder  # cache in local variables, which are presumably faster
    vocab_decoder = _vocab_decoder
    hint_decoder = _hint_decoder

    with zstandard.open(hints_file_path, 'rt') if hints_file_path.suffix == '.zst' else open(hints_file_path) as f:
        preamble = try_parse_json_line(next(f), preamble_decoder)
        if preamble.format != FORMAT_NAME:
            raise RuntimeError(
                f'Failed to parse hint bundle preamble: expected format "{FORMAT_NAME}", instead got '
                + repr(preamble.format)
            )
        vocab = try_parse_json_line(next(f), vocab_decoder)
        hints = [try_parse_json_line(s, hint_decoder) for s in _lines_range(f, begin_index, end_index)]
    return HintBundle(hints=hints, pass_name=preamble.pass_, vocabulary=[s.encode() for s in vocab])


def subtract_hints(source_bundle: HintBundle, bundles_to_subtract: List[HintBundle]) -> HintBundle:
    """Transforms source_bundle as if all hints from bundles_to_subtract have been applied.

    This gives recalculated hints that are applicable to the transformed input files.
    """
    # Group patches and positions we're interested in by the file path.
    path_to_queries: Dict[Path, List[int]] = {}
    for hint in source_bundle.hints:
        for patch in hint.patches:
            file_rel = Path(source_bundle.vocabulary[patch.file].decode()) if patch.file is not None else Path()
            path_to_queries.setdefault(file_rel, []).extend((patch.left, patch.right))
    path_to_subtrahends: Dict[Path, List[_PatchWithBundleRef]] = {}
    for bundle_id, bundle in enumerate(bundles_to_subtract):
        for hint in bundle.hints:
            for patch in hint.patches:
                p = _PatchWithBundleRef(patch, bundle_id)
                file_rel = Path(bundle.vocabulary[patch.file].decode()) if patch.file is not None else Path()
                path_to_subtrahends.setdefault(file_rel, []).append(p)

    # Calculate how positions in each file shift after applying the subtrahend hints.
    path_to_positions_mapping: Dict[Path, Dict[int, int]] = {}
    for path, queries in path_to_queries.items():
        path_to_positions_mapping[path] = _calc_positions_mapping_for_patches(
            queries, path_to_subtrahends.get(path, []), bundles_to_subtract
        )

    # Build new hints with the updated positions.
    new_hints = []
    for hint in source_bundle.hints:
        new_patches = []
        for patch in hint.patches:
            file_rel = Path(source_bundle.vocabulary[patch.file].decode()) if patch.file is not None else Path()
            mapping = path_to_positions_mapping[file_rel]
            new_patch = msgspec.structs.replace(patch, left=mapping[patch.left], right=mapping[patch.right])
            if (
                new_patch.left < new_patch.right
                or new_patch.left == new_patch.right
                and new_patch.operation is not None
            ):
                new_patches.append(new_patch)
        if new_patches or hint.type is not None and is_special_hint_type(source_bundle.vocabulary[hint.type]):
            new_hints.append(msgspec.structs.replace(hint, patches=tuple(new_patches)))
    return HintBundle(hints=new_hints, pass_name=source_bundle.pass_name, vocabulary=source_bundle.vocabulary)


def _calc_positions_mapping_for_patches(
    queries: Sequence[int], patches: Sequence[_PatchWithBundleRef], bundles: Sequence[HintBundle]
) -> Dict[int, int]:
    positions_mapping: Dict[int, int] = {}
    merged_patches = _merge_overlapping_patches(patches)
    ptr = 0
    position_delta = 0
    for query in sorted(set(queries)):
        # Apply patches up until the current position.
        while ptr < len(merged_patches) and merged_patches[ptr].patch.right <= query:
            patch_ref = merged_patches[ptr]
            to_delete = patch_ref.patch.right - patch_ref.patch.left
            to_insert = (
                0
                if patch_ref.patch.value is None
                else len(bundles[patch_ref.bundle_id].vocabulary[patch_ref.patch.value])
            )
            position_delta += to_insert - to_delete
            ptr += 1
        new_pos = query + position_delta
        if ptr < len(merged_patches) and merged_patches[ptr].patch.left < query:
            # Adjust if we're inside another patch.
            to_delete = query - merged_patches[ptr].patch.left
            new_pos -= to_delete
        positions_mapping[query] = new_pos
    return positions_mapping


def group_hints_by_type(bundle: HintBundle) -> Dict[bytes, HintBundle]:
    """Splits the bundle into multiple, one per each hint type."""
    grouped: Dict[bytes, HintBundle] = {}
    for h in bundle.hints:
        type = bundle.vocabulary[h.type] if h.type is not None else b''
        if type not in grouped:
            grouped[type] = HintBundle(vocabulary=bundle.vocabulary, hints=[], pass_name=bundle.pass_name)
        # FIXME: drop the 't' property in favor of storing it once, in the bundle's preamble
        grouped[type].hints.append(h)
    return grouped


def make_preamble(bundle: HintBundle) -> _BundlePreamble:
    return _BundlePreamble(format=FORMAT_NAME, pass_=bundle.pass_name)


def write_compact_json(value: Any, file: TextIO) -> None:
    """Writes a JSON dump, as a compact representation (without unnecessary spaces), to the file.

    Skips circular structure checks, for performance reasons."""
    # Specify custom separators - the default ones have spaces after them.
    json.dump(value, file, check_circular=False, separators=(',', ':'))


def try_parse_json_line(text: str, decoder: msgspec.json.Decoder) -> Any:
    try:
        return decoder.decode(text)
    except msgspec.MsgspecError as e:
        raise RuntimeError(f'Failed to decode line "{text}": {e}') from e


def _merge_overlapping_patches(patches: Sequence[_PatchWithBundleRef]) -> Sequence[_PatchWithBundleRef]:
    """Returns non-overlapping hint patches, merging patches where necessary."""

    def sorting_key(p: _PatchWithBundleRef):
        is_replacement = p.patch.value is not None
        # Among all patches starting in the same location, use additional criteria:
        # * prefer seeing larger patches first, hence sort by decreasing "r";
        # * (if still a tie) prefer deletion over text replacement.
        return p.patch.left, -p.patch.right, is_replacement

    merged: List[_PatchWithBundleRef] = []
    for cur in sorted(patches, key=sorting_key):
        if merged:
            prev = merged[-1]
            if max(prev.patch.left, cur.patch.left) < min(prev.patch.right, cur.patch.right):
                # There's an overlap with the previous patch; note that only real overlaps (with at least one common
                # character) are detected. Extend the previous patch to fit the new patch.
                if cur.patch.right > prev.patch.right:
                    prev.patch = msgspec.structs.replace(prev.patch, right=cur.patch.right)
                continue
        # No overlap with previous items - just add the new patch.
        merged.append(cur)
    return merged


def _lines_range(f: TextIO, begin_index: Optional[int], end_index: Optional[int]) -> List[str]:
    for _ in range(begin_index or 0):
        next(f)  # simply discard
    if end_index is None:
        return list(f)
    cnt = end_index - (begin_index or 0)
    return [next(f) for _ in range(cnt)]


def _mkdir_up_to(dir_to_create: Path, last_parent_dir: Path) -> None:
    """Similar to Path.mkdir(parents=True), but stops at the given ancestor directory.

    We use it to avoid canceled-but-not-killed-yet C-Vise jobs recreating temporary work directories that the C-Vise
    main process has deleted.
    """
    assert dir_to_create.is_relative_to(last_parent_dir)
    if dir_to_create != last_parent_dir:
        _mkdir_up_to(dir_to_create.parent, last_parent_dir)
    dir_to_create.mkdir(exist_ok=True)

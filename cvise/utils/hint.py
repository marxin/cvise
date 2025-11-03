"""Helpers for working with "hints" - descriptions of edits to be attempted.

A hint is a compact JSON object that describes one or multiple modifications of
the input: deletion of text at a particular location, replacement with new
text, etc.

The usage of hints, as a protocol, allows to simplify implementing reduction
heuristics and to perform reduction more efficiently (as algorithms can now be
applied to all heuristics in a uniform way).
"""

from __future__ import annotations

import dataclasses
import json
import math
from collections.abc import Sequence
from copy import deepcopy
from pathlib import Path
from typing import Any, TextIO

import msgspec
import zstandard

# Currently just a hardcoded constant - the number is reserved for backwards-incompatible format changes in the future.
FORMAT_NAME = 'cvise_hints_v0'


class Patch(msgspec.Struct, omit_defaults=True, gc=False, frozen=True):
    """Describes a single patch inside a hint.

    See HINT_PATCH_SCHEMA.
    """

    path: int | None = msgspec.field(default=None, name='p')
    left: int | None = msgspec.field(default=None, name='l')
    right: int | None = msgspec.field(default=None, name='r')
    operation: int | None = msgspec.field(default=None, name='o')
    value: int | None = msgspec.field(default=None, name='v')

    def comparison_key(self) -> tuple:
        return (
            -1 if self.path is None else self.path,
            -1 if self.left is None else self.left,
            -1 if self.right is None else self.right,
            -1 if self.operation is None else self.operation,
            -1 if self.value is None else self.value,
        )


class Hint(msgspec.Struct, omit_defaults=True, gc=False, frozen=True):
    """Describes a single hint.

    See HINT_SCHEMA.
    """

    type: int | None = msgspec.field(default=None, name='t')
    patches: tuple[Patch, ...] = msgspec.field(default=(), name='p')
    extra: int | None = msgspec.field(default=None, name='e')

    def comparison_key(self) -> tuple:
        return (
            -1 if self.type is None else self.type,
            tuple(p.comparison_key() for p in self.patches),
            -1 if self.extra is None else self.extra,
        )


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
    hints: list[Hint]
    pass_name: str = ''
    pass_user_visible_name: str = ''
    # Strings that hints can refer to.
    # Note: a simple "= []" wouldn't be suitable because mutable default values are error-prone in Python.
    vocabulary: list[bytes] = dataclasses.field(default_factory=list)


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
                "'character). Must be specified iff 'l' is, and must be greater than or equal to 'l'."
            ),
            'type': 'integer',
        },
        'p': {
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
                'the index in the vocabulary. The only currently supported operation are "rm" - deleting the file, '
                '"paste" - inserting .'
            ),
            'type': 'integer',
            'minimum': 0,
        },
        'v': {
            'description': (
                'By default, indicates that the chunk needs to be replaced with a new value - the string with the '
                'specified index in the vocabulary. For "paste" operations, specifies the path of the file which '
                'contents are to be used as a replacement.'
            ),
            'type': 'integer',
            'minimum': 0,
        },
    },
}

HINT_PATCH_SCHEMA_STRICT = deepcopy(HINT_PATCH_SCHEMA)
HINT_PATCH_SCHEMA_STRICT['additionalProperties'] = False

HINT_SCHEMA = {
    'description': 'Hint object - a description of modification(s) of the input',
    'type': 'object',
    'properties': {
        'p': {
            'description': 'Patches that this hint consists of.',
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
class HintApplicationReport:
    stats_delta_per_pass: dict[str, int]
    written_paths: set[Path]

    def get_passes_ordered_by_delta(self) -> list[str]:
        ordered = sorted(self.stats_delta_per_pass.items(), key=lambda kv: kv[1])
        return [kv[0] for kv in ordered]


class _BundlePreamble(msgspec.Struct, omit_defaults=True):
    format: str  # the FORMAT_NAME default is not set here, to avoid being omitted by msgspec serialization
    pass_name: str = ''
    pass_user_visible_name: str = ''


# Singleton encoder/decoder objects, to save time on recreating them.
_json_encoder: msgspec.json.Encoder | None = None
_encoding_buf: bytearray | None = None
_preamble_decoder: msgspec.json.Decoder | None = None
_vocab_decoder: msgspec.json.Decoder | None = None
_hint_decoder: msgspec.json.Decoder | None = None


def is_special_hint_type(type: bytes) -> bool:
    return type.startswith(b'@')


class _PatchWithBundleRef(msgspec.Struct, gc=False):
    patch: Patch
    bundle_id: int
    hint_id: int


def apply_hints(bundles: list[HintBundle], source_path: Path, destination_path: Path) -> HintApplicationReport | None:
    """Creates the destination file/dir by applying the specified hints to the contents of the source file/dir.

    Returns None on an unsolvable merge conflict - e.g., one hint pasting a context of a file that gets modified by
    another hint.
    """
    is_dir = source_path.is_dir()
    if is_dir:
        destination_path.mkdir(exist_ok=True)
        assert list(destination_path.iterdir()) == []

    # Take patches from all hints and group them by the file/dir path which they're applied to.
    path_to_patches: dict[Path, list[_PatchWithBundleRef]] = {}
    for bundle_id, bundle in enumerate(bundles):
        for hint_id, hint in enumerate(bundle.hints):
            for patch in hint.patches:
                p = _PatchWithBundleRef(patch, bundle_id, hint_id)
                path_rel = Path(bundle.vocabulary[patch.path].decode()) if patch.path is not None else Path()
                path_to_patches.setdefault(path_rel, []).append(p)

    # Enumerate all files in the source location and apply corresponding patches, if any, to each.
    subtree = sorted(source_path.rglob('*')) if is_dir else [source_path]
    report = HintApplicationReport(stats_delta_per_pass={}, written_paths=set())
    for path in subtree:
        path_rel = path.relative_to(source_path)
        path_in_dest = destination_path / path_rel
        patches_to_apply = path_to_patches.get(path_rel, [])

        if _take_rm_patch(patches_to_apply, bundles, path, report.stats_delta_per_pass):
            continue  # skip creating the file/dir
        if path.is_symlink():
            continue  # TODO: handle symlinks
        report.written_paths.add(path_in_dest)
        if path.is_dir():
            # The sorted path order guarantees the parents should've been created.
            path_in_dest.mkdir()
            continue
        if not _apply_hint_patches_to_file(
            patches_to_apply,
            bundles,
            test_case=source_path,
            source_file=path,
            destination_file=path_in_dest,
            path_to_patches=path_to_patches,
            stats_delta_per_pass=report.stats_delta_per_pass,
        ):
            return None
    return report


def _take_rm_patch(
    patches: list[_PatchWithBundleRef],
    bundles: list[HintBundle],
    source_file: Path,
    stats_delta_per_pass: dict[str, int],
) -> bool:
    for patch_ref in patches:
        p: Patch = patch_ref.patch
        bundle: HintBundle = bundles[patch_ref.bundle_id]
        if p.operation is None:
            continue
        if bundle.vocabulary[p.operation] != b'rm':
            continue
        stats_delta_per_pass.setdefault(bundle.pass_user_visible_name, 0)
        if source_file.is_file():
            stats_delta_per_pass[bundle.pass_user_visible_name] -= source_file.lstat().st_size
        return True
    return False


def _apply_hint_patches_to_file(
    patches: list[_PatchWithBundleRef],
    bundles: list[HintBundle],
    test_case: Path,
    source_file: Path,
    destination_file: Path,
    path_to_patches: dict[Path, list[_PatchWithBundleRef]],
    stats_delta_per_pass: dict[str, int],
) -> bool:
    merged_patches = _merge_overlapping_patches(patches)
    orig_data = memoryview(source_file.read_bytes())

    new_data = bytearray()
    start_pos = 0
    for patch_ref in merged_patches:
        p: Patch = patch_ref.patch
        bundle: HintBundle = bundles[patch_ref.bundle_id]
        stats_delta_per_pass.setdefault(bundle.pass_user_visible_name, 0)
        try:
            assert p.left is not None
            assert p.right is not None
            assert start_pos <= p.left <= len(orig_data)
            assert p.left <= p.right <= len(orig_data)
            # Add the unmodified chunk up to the current patch begin.
            new_data.extend(orig_data[start_pos : p.left])
            # Skip the original chunk inside the current patch.
            start_pos = p.right
            stats_delta_per_pass[bundle.pass_user_visible_name] -= p.right - p.left
            # Insert the replacement value, if provided.
            if p.value is not None:
                if p.operation is not None and bundle.vocabulary[p.operation] == b'paste':
                    ins_path = Path(bundle.vocabulary[p.value].decode())
                    if _has_patches_from_other_hints(patch_ref, path_to_patches.get(ins_path, [])):
                        return False  # merge conflict that's unsolvable (in the current implementation)
                    to_insert = (test_case / ins_path).read_bytes()
                else:
                    to_insert = bundle.vocabulary[p.value]
                new_data += to_insert
                stats_delta_per_pass[bundle.pass_user_visible_name] += len(to_insert)
        except Exception as e:
            raise RuntimeError(
                f'Failure while applying patch {p} from pass "{bundle.pass_name}" on file "{source_file}" with size {len(orig_data)}'
            ) from e
    # Add the unmodified chunk after the last patch end.
    new_data.extend(orig_data[start_pos:])

    destination_file.write_bytes(new_data)
    return True


def _has_patches_from_other_hints(ref: _PatchWithBundleRef, other_refs: list[_PatchWithBundleRef]) -> bool:
    return any(o.bundle_id != ref.bundle_id or o.hint_id != ref.hint_id for o in other_refs)


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
    assert encoder is not None
    assert buf is not None

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


def load_hints(hints_file_path: Path, begin_index: int | None, end_index: int | None) -> HintBundle:
    """Deserializes hints from a file.

    If provided, the [begin; end) half-range can be used to only load hints with the specified indices.

    Whether the hints file is compressed is determined based on the file extension."""
    if begin_index is not None and end_index is not None:
        assert begin_index < end_index

    global _preamble_decoder, _vocab_decoder, _hint_decoder
    if _preamble_decoder is None:  # lazily initialize singletons
        _preamble_decoder = msgspec.json.Decoder(type=_BundlePreamble)
        _vocab_decoder = msgspec.json.Decoder(type=list[str])
        _hint_decoder = msgspec.json.Decoder(type=Hint)
    preamble_decoder = _preamble_decoder  # cache in local variables, which are presumably faster
    vocab_decoder = _vocab_decoder
    hint_decoder = _hint_decoder
    assert preamble_decoder
    assert vocab_decoder
    assert hint_decoder

    with zstandard.open(hints_file_path, 'rt') if hints_file_path.suffix == '.zst' else open(hints_file_path) as f:
        preamble = try_parse_json_line(next(f), preamble_decoder)
        if preamble.format != FORMAT_NAME:
            raise RuntimeError(
                f'Failed to parse hint bundle preamble: expected format "{FORMAT_NAME}", instead got '
                + repr(preamble.format)
            )
        vocab = try_parse_json_line(next(f), vocab_decoder)
        hints = [try_parse_json_line(s, hint_decoder) for s in _lines_range(f, begin_index, end_index)]
    return HintBundle(
        hints=hints,
        pass_name=preamble.pass_name,
        pass_user_visible_name=preamble.pass_user_visible_name,
        vocabulary=[s.encode() for s in vocab],
    )


def subtract_hints(source_bundle: HintBundle, bundles_to_subtract: list[HintBundle]) -> HintBundle:
    """Transforms source_bundle as if all hints from bundles_to_subtract have been applied.

    This gives recalculated hints that are applicable to the transformed input files.
    """
    # Group patches and positions we're interested in by the file path.
    path_to_queries: dict[Path, list[int]] = {}
    for hint in source_bundle.hints:
        for patch in hint.patches:
            path_rel = Path(source_bundle.vocabulary[patch.path].decode()) if patch.path is not None else Path()
            queries = path_to_queries.setdefault(path_rel, [])
            if patch.left is not None:
                queries.append(patch.left)
            if patch.right is not None:
                queries.append(patch.right)
    path_to_subtrahends: dict[Path, list[_PatchWithBundleRef]] = {}
    for bundle_id, bundle in enumerate(bundles_to_subtract):
        for hint_id, hint in enumerate(bundle.hints):
            for patch in hint.patches:
                p = _PatchWithBundleRef(patch, bundle_id, hint_id)
                path_rel = Path(bundle.vocabulary[patch.path].decode()) if patch.path is not None else Path()
                path_to_subtrahends.setdefault(path_rel, []).append(p)

    # Calculate how positions in each file shift after applying the subtrahend hints.
    path_to_positions_mapping: dict[Path, dict[int, int]] = {}
    for path, queries in path_to_queries.items():
        path_to_positions_mapping[path] = _calc_positions_mapping_for_patches(
            queries, path_to_subtrahends.get(path, []), bundles_to_subtract
        )

    # Build new hints with the updated positions.
    new_hints = []
    for hint in source_bundle.hints:
        new_patches = []
        for patch in hint.patches:
            path_rel = Path(source_bundle.vocabulary[patch.path].decode()) if patch.path is not None else Path()
            mapping = path_to_positions_mapping[path_rel]
            new_patch = msgspec.structs.replace(
                patch,
                left=None if patch.left is None else mapping[patch.left],
                right=None if patch.right is None else mapping[patch.right],
            )
            if (
                new_patch.left is None
                or new_patch.right is None
                or new_patch.left < new_patch.right
                or new_patch.left == new_patch.right
                and new_patch.operation is not None
            ):
                new_patches.append(new_patch)
        new_hints.append(msgspec.structs.replace(hint, patches=tuple(new_patches)))
    return HintBundle(
        hints=new_hints,
        pass_name=source_bundle.pass_name,
        pass_user_visible_name=source_bundle.pass_user_visible_name,
        vocabulary=source_bundle.vocabulary,
    )


def _calc_positions_mapping_for_patches(
    queries: Sequence[int], patches: Sequence[_PatchWithBundleRef], bundles: Sequence[HintBundle]
) -> dict[int, int]:
    positions_mapping: dict[int, int] = {}
    merged_patches = _merge_overlapping_patches(patches)
    ptr = 0
    position_delta = 0
    for query in sorted(set(queries)):
        # Apply patches up until the current position.
        while ptr < len(merged_patches) and (merged_patches[ptr].patch.right or 0) <= query:
            ref = merged_patches[ptr]
            patch = ref.patch
            if patch.left is not None and patch.right is not None:
                to_delete = patch.right - patch.left
                to_insert = 0 if patch.value is None else len(bundles[ref.bundle_id].vocabulary[patch.value])
                position_delta += to_insert - to_delete
            ptr += 1
        new_pos = query + position_delta

        # Adjust if we're inside another patch.
        next_left = merged_patches[ptr].patch.left if ptr < len(merged_patches) else None
        if next_left is not None and next_left < query:
            to_delete = query - next_left
            new_pos -= to_delete

        positions_mapping[query] = new_pos
    return positions_mapping


def group_hints_by_type(bundle: HintBundle) -> dict[bytes, HintBundle]:
    """Splits the bundle into multiple, one per each hint type."""
    grouped: dict[bytes, HintBundle] = {}
    for h in bundle.hints:
        type = bundle.vocabulary[h.type] if h.type is not None else b''
        if type not in grouped:
            grouped[type] = HintBundle(
                vocabulary=bundle.vocabulary,
                hints=[],
                pass_name=bundle.pass_name,
                pass_user_visible_name=bundle.pass_user_visible_name,
            )
        # FIXME: drop the 't' property in favor of storing it once, in the bundle's preamble
        grouped[type].hints.append(h)
    return grouped


def make_preamble(bundle: HintBundle) -> _BundlePreamble:
    return _BundlePreamble(
        format=FORMAT_NAME, pass_name=bundle.pass_name, pass_user_visible_name=bundle.pass_user_visible_name
    )


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


def sort_hints(bundle: HintBundle) -> None:
    # First, sort patches in each hint.
    for i, hint in enumerate(bundle.hints):
        if not hint.patches:
            continue
        need_sort = False
        prev_key = hint.patches[0].comparison_key()
        for p in hint.patches[1:]:
            key = p.comparison_key()
            if prev_key > key:
                need_sort = True
                break
            prev_key = key
        if not need_sort:
            continue
        new_patches = tuple(sorted(hint.patches, key=Patch.comparison_key))
        bundle.hints[i] = msgspec.structs.replace(hint, patches=new_patches)

    # Then sort hints in the bundle.
    bundle.hints.sort(key=Hint.comparison_key)


def _merge_overlapping_patches(patches: Sequence[_PatchWithBundleRef]) -> Sequence[_PatchWithBundleRef]:
    """Returns non-overlapping hint patches, merging patches where necessary."""
    merged: list[_PatchWithBundleRef] = []
    for cur in sorted(patches, key=_patch_merge_sorting_key):
        if merged:
            prev = merged[-1]
            prev_p = prev.patch
            cur_p = cur.patch
            if (
                prev_p.left is not None
                and prev_p.right is not None
                and cur_p.left is not None
                and cur_p.right is not None
                and max(prev_p.left, cur_p.left) < min(prev_p.right, cur_p.right)
            ):
                # There's an overlap with the previous patch; note that only real overlaps (with at least one common
                # character) are detected. Extend the previous patch to fit the new patch.
                if cur_p.right > prev_p.right:
                    prev.patch = msgspec.structs.replace(prev.patch, right=cur_p.right)
                continue
        # No overlap with previous items - just add the new patch.
        merged.append(cur)
    return merged


def _patch_merge_sorting_key(ref: _PatchWithBundleRef):
    """Sorting key used for merging overlapping patches."""
    p = ref.patch
    is_replacement = p.value is not None
    # Criteria:
    # * prefer seeing positionless patches (without left/right) first;
    # * positioned patches should be first sorted by their left;
    # * prefer seeing larger patches first, hence sort by decreasing "r";
    # * (if still a tie) prefer deletion over text replacement.
    return (
        -math.inf if p.left is None else p.left,
        -math.inf if p.right is None else -p.right,
        is_replacement,
    )


def _lines_range(f: TextIO, begin_index: int | None, end_index: int | None) -> list[str]:
    for _ in range(begin_index or 0):
        next(f)  # simply discard
    if end_index is None:
        return list(f)
    cnt = end_index - (begin_index or 0)
    return [next(f) for _ in range(cnt)]

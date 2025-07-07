"""Helpers for working with "hints" - descriptions of edits to be attempted.

A hint is a compact JSON object that describes one or multiple modifications of
the input: deletion of text at a particular location, replacement with new
text, etc.

The usage of hints, as a protocol, allows to simplify implementing reduction
heuristics and to perform reduction more efficiently (as algorithms can now be
applied to all heuristics in a uniform way).
"""

from dataclasses import dataclass
import json
from pathlib import Path
from typing import List, Sequence
import zstandard


@dataclass
class HintBundle:
    """Stores a collection of hints.

    Its standard serialization format is a newline-separated JSON of the following structure:

      <Hint 1 object>\n
      <Hint 2 object>\n
      ...
    """

    # Hint objects - each item matches the `HINT_SCHEMA`.
    hints: List[object]


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


def apply_hints(hints: HintBundle, file: Path) -> str:
    """Edits the file applying the specified hints to its contents."""
    patches = sum((h['p'] for h in hints.hints), start=[])
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
        # Delete the chunk inside the current patch.
        start_pos = right
    # Add the unmodified chunk after the last patch end.
    new_data += orig_data[start_pos:]
    return new_data


def store_hints(hints: HintBundle, hints_file_path: Path) -> None:
    """Serializes hints to the given file.

    We currently use the Zstandard compression to reduce the space usage (the empirical compression ratio observed for
    hint JSONs is around 5x..20x)."""
    with zstandard.open(hints_file_path, 'wt') as f:
        for h in hints.hints:
            # Skip checks and omit spaces around separators, for the sake of performance.
            json.dump(h, f, check_circular=False, separators=(',', ':'))
            f.write('\n')


def load_hints(hints_file_path: Path, begin_index: int, end_index: int) -> HintBundle:
    """Deserializes hints with the given indices [begin; end) from a file.

    Whether the hints file is compressed is determined based on the file extension."""
    assert begin_index < end_index
    hints = []
    with zstandard.open(hints_file_path, 'rt') if hints_file_path.suffix == '.zst' else open(hints_file_path) as f:
        for i, line in enumerate(f):
            if begin_index <= i < end_index:
                try:
                    hints.append(json.loads(line))
                except json.decoder.JSONDecodeError as e:
                    raise RuntimeError(f'Failed to decode line "{line}": {e}') from e
    return HintBundle(hints=hints)


def merge_overlapping_patches(patches: Sequence[object]) -> Sequence[object]:
    """Returns non-overlapping hint patches, merging patches where necessary."""

    def sorting_key(patch):
        return patch['l']

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

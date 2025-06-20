"""Helpers for working with "hints" - descriptions of edits to be attempted.

A hint is a compact JSON object that describes one or multiple modifications of
the input: deletion of text at a particular location, replacement with new
text, etc.

The usage of hints, as a protocol, allows to simplify implementing reduction
heuristics and to perform reduction more efficiently (as algorithms can now be
applied to all heuristics in a uniform way).
"""

from pathlib import Path
from typing import Sequence

# JSON Schemas:

HINT_PLACE_SCHEMA = {
    'description': 'Hint place object, describing a simple patch to be applied to the input. By default, unless a specific property is specified, a place deletes the specified chunk',
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
            'description': 'Places where the hint is to be applied',
            'type': 'array',
            'items': HINT_PLACE_SCHEMA,
            'minItems': 1,
        },
    },
    'required': ['p'],
}


def apply_hints(hints: Sequence[object], file: Path) -> None:
    """Edits the file applying the specified hints to its contents."""
    places = sum((h['p'] for h in hints), start=[])
    merged_places = merge_overlapping_places(places)

    with open(file) as f:
        orig_data = f.read()

    new_data = ''
    start_pos = 0
    for p in merged_places:
        left = p['l']
        right = p['r']
        assert start_pos <= left < len(orig_data)
        assert left < right <= len(orig_data)
        # Add the chunk up to the current beginning unmodified.
        new_data += orig_data[start_pos:left]
        # Delete the chunk inside the current edit.
        start_pos = right
    # Add unmodified the chunk after the last edit"s end.
    new_data += orig_data[start_pos:]

    with open(file, 'w') as f:
        f.write(new_data)


def merge_overlapping_places(places: Sequence[object]) -> Sequence[object]:
    """Returns non-overlapping hint places, merging places where necessary."""

    def sorting_key(place):
        return place['l']

    merged = []
    for place in sorted(places, key=sorting_key):
        if merged and places_overlap(merged[-1], place):
            extend_to_fit(merged[-1], place)
        else:
            merged.append(place)
    return merged


def places_overlap(first: object, second: object) -> bool:
    """Checks whether two places overlap.

    Only real overlaps (with at least one common position) are counted - False
    is returned for places merely touching each other.
    """
    return max(first['l'], second['l']) < min(first['r'], second['r'])


def extend_to_fit(place: object, appended_place: object) -> None:
    """Modifies the first place so that the second place fits into it."""
    place['r'] = max(place['r'], appended_place['r'])

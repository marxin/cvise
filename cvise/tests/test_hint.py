import json
import jsonschema
import pytest

from cvise.utils.hint import apply_hints, load_hints, store_hints, HINT_SCHEMA


@pytest.fixture
def tmp_file(tmp_path):
    return tmp_path / 'file.txt'


def test_apply_hints_delete_prefix(tmp_file):
    tmp_file.write_text('Foo bar')
    hint = {'p': [{'l': 0, 'r': 4}]}
    jsonschema.validate(hint, schema=HINT_SCHEMA)

    apply_hints([hint], tmp_file)

    assert tmp_file.read_text() == 'bar'


def test_apply_hints_delete_suffix(tmp_file):
    tmp_file.write_text('Foo bar')
    hint = {'p': [{'l': 3, 'r': 7}]}
    jsonschema.validate(hint, schema=HINT_SCHEMA)

    apply_hints([hint], tmp_file)

    assert tmp_file.read_text() == 'Foo'


def test_apply_hints_delete_middle(tmp_file):
    tmp_file.write_text('Foo bar baz')
    hint = {'p': [{'l': 3, 'r': 7}]}
    jsonschema.validate(hint, schema=HINT_SCHEMA)

    apply_hints([hint], tmp_file)

    assert tmp_file.read_text() == 'Foo baz'


def test_apply_hints_delete_middle_multiple(tmp_file):
    tmp_file.write_text('Foo bar baz')
    hint1 = {'p': [{'l': 3, 'r': 4}]}
    hint2 = {'p': [{'l': 7, 'r': 8}]}
    hints = [hint1, hint2]
    for h in hints:
        jsonschema.validate(h, schema=HINT_SCHEMA)

    apply_hints(hints, tmp_file)

    assert tmp_file.read_text() == 'Foobarbaz'


def test_apply_hints_delete_all(tmp_file):
    tmp_file.write_text('Foo bar')
    hint = {'p': [{'l': 0, 'r': 7}]}
    jsonschema.validate(hint, schema=HINT_SCHEMA)

    apply_hints([hint], tmp_file)

    assert tmp_file.read_text() == ''


def test_apply_hints_delete_touching(tmp_file):
    tmp_file.write_text('Foo bar baz')
    # It's essentially the deletion of [3..7).
    hint1 = {'p': [{'l': 3, 'r': 4}]}
    hint2 = {'p': [{'l': 6, 'r': 7}]}
    hint3 = {'p': [{'l': 5, 'r': 6}, {'l': 4, 'r': 5}]}
    hints = [hint1, hint2, hint3]
    for h in hints:
        jsonschema.validate(h, schema=HINT_SCHEMA)

    apply_hints(hints, tmp_file)

    assert tmp_file.read_text() == 'Foo baz'


def test_apply_hints_delete_overlapping(tmp_file):
    tmp_file.write_text('Foo bar baz')
    # It's essentially the deletion of [3..7).
    hint1 = {'p': [{'l': 3, 'r': 6}]}
    hint2 = {'p': [{'l': 4, 'r': 7}]}
    hints = [hint1, hint2]
    for h in hints:
        jsonschema.validate(h, schema=HINT_SCHEMA)

    apply_hints(hints, tmp_file)

    assert tmp_file.read_text() == 'Foo baz'


def test_apply_hints_delete_nested(tmp_file):
    tmp_file.write_text('Foo bar baz')
    hint1 = {'p': [{'l': 4, 'r': 6}]}
    hint2 = {'p': [{'l': 3, 'r': 7}]}
    hints = [hint1, hint2]
    for h in hints:
        jsonschema.validate(h, schema=HINT_SCHEMA)

    apply_hints(hints, tmp_file)

    assert tmp_file.read_text() == 'Foo baz'


def test_store_load_hints(tmp_file):
    hint1 = {'p': [{'l': 0, 'r': 1}]}
    hint2 = {'p': [{'l': 2, 'r': 3}, {'l': 4, 'r': 5}]}
    store_hints([hint1, hint2], tmp_file)

    assert load_hints(tmp_file, 0, 2) == [hint1, hint2]
    assert load_hints(tmp_file, 0, 1) == [hint1]
    assert load_hints(tmp_file, 1, 2) == [hint2]


def test_hints_storage_compression(tmp_file):
    COUNT = 10000
    hints = [{'p': [{'l': i, 'r': i + 1}]} for i in range(COUNT)]
    store_hints(hints, tmp_file)

    # Check that the file is significantly smaller than a regular JSON representation (without extra spaces around
    # separators).
    RATIO_AT_LEAST = 10
    hints_json_size = len(json.dumps(hints, separators=(',', ':')))
    assert tmp_file.stat().st_size * RATIO_AT_LEAST < hints_json_size

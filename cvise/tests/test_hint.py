import json
import jsonschema
import pytest

from cvise.utils.hint import apply_hints, HintBundle, load_hints, store_hints, HINT_SCHEMA


@pytest.fixture
def tmp_file(tmp_path):
    return tmp_path / 'file.txt'


@pytest.fixture
def tmp_hints_file(tmp_path):
    return tmp_path / 'hints.zst'


def test_apply_hints_delete_prefix(tmp_file):
    tmp_file.write_text('Foo bar')
    hint = {'p': [{'l': 0, 'r': 4}]}
    jsonschema.validate(hint, schema=HINT_SCHEMA)
    bundle = HintBundle(hints=[hint])

    new_data = apply_hints(bundle, tmp_file)

    assert new_data == 'bar'


def test_apply_hints_delete_suffix(tmp_file):
    tmp_file.write_text('Foo bar')
    hint = {'p': [{'l': 3, 'r': 7}]}
    jsonschema.validate(hint, schema=HINT_SCHEMA)
    bundle = HintBundle(hints=[hint])

    new_data = apply_hints(bundle, tmp_file)

    assert new_data == 'Foo'


def test_apply_hints_delete_middle(tmp_file):
    tmp_file.write_text('Foo bar baz')
    hint = {'p': [{'l': 3, 'r': 7}]}
    jsonschema.validate(hint, schema=HINT_SCHEMA)
    bundle = HintBundle(hints=[hint])

    new_data = apply_hints(bundle, tmp_file)

    assert new_data == 'Foo baz'


def test_apply_hints_delete_middle_multiple(tmp_file):
    tmp_file.write_text('Foo bar baz')
    hint1 = {'p': [{'l': 3, 'r': 4}]}
    hint2 = {'p': [{'l': 7, 'r': 8}]}
    hints = [hint1, hint2]
    for h in hints:
        jsonschema.validate(h, schema=HINT_SCHEMA)
    bundle = HintBundle(hints=hints)

    new_data = apply_hints(bundle, tmp_file)

    assert new_data == 'Foobarbaz'


def test_apply_hints_delete_all(tmp_file):
    tmp_file.write_text('Foo bar')
    hint = {'p': [{'l': 0, 'r': 7}]}
    jsonschema.validate(hint, schema=HINT_SCHEMA)
    bundle = HintBundle(hints=[hint])

    new_data = apply_hints(bundle, tmp_file)

    assert new_data == ''


def test_apply_hints_delete_touching(tmp_file):
    tmp_file.write_text('Foo bar baz')
    # It's essentially the deletion of [3..7).
    hint1 = {'p': [{'l': 3, 'r': 4}]}
    hint2 = {'p': [{'l': 6, 'r': 7}]}
    hint3 = {'p': [{'l': 5, 'r': 6}, {'l': 4, 'r': 5}]}
    hints = [hint1, hint2, hint3]
    for h in hints:
        jsonschema.validate(h, schema=HINT_SCHEMA)
    bundle = HintBundle(hints=hints)

    new_data = apply_hints(bundle, tmp_file)

    assert new_data == 'Foo baz'


def test_apply_hints_delete_overlapping(tmp_file):
    tmp_file.write_text('Foo bar baz')
    # It's essentially the deletion of [3..7).
    hint1 = {'p': [{'l': 3, 'r': 6}]}
    hint2 = {'p': [{'l': 4, 'r': 7}]}
    hints = [hint1, hint2]
    for h in hints:
        jsonschema.validate(h, schema=HINT_SCHEMA)
    bundle = HintBundle(hints=hints)

    new_data = apply_hints(bundle, tmp_file)

    assert new_data == 'Foo baz'


def test_apply_hints_delete_nested(tmp_file):
    tmp_file.write_text('Foo bar baz')
    hint1 = {'p': [{'l': 4, 'r': 6}]}
    hint2 = {'p': [{'l': 3, 'r': 7}]}
    hints = [hint1, hint2]
    for h in hints:
        jsonschema.validate(h, schema=HINT_SCHEMA)
    bundle = HintBundle(hints=hints)

    new_data = apply_hints(bundle, tmp_file)

    assert new_data == 'Foo baz'


def test_apply_hints_replace_with_shorter(tmp_file):
    """Test a hint replacing a fragment with a shorter value."""
    tmp_file.write_text('Foo bar baz')
    vocab = ['x']
    hint = {'p': [{'l': 4, 'r': 7, 'v': 0}]}
    jsonschema.validate(hint, schema=HINT_SCHEMA)
    bundle = HintBundle(vocabulary=vocab, hints=[hint])

    new_data = apply_hints(bundle, tmp_file)

    assert new_data == 'Foo x baz'


def test_apply_hints_replace_with_longer(tmp_file):
    """Test a hint replacing a fragment with a longer value."""
    tmp_file.write_text('Foo x baz')
    vocab = ['x', 'bar']
    hint = {'p': [{'l': 4, 'r': 5, 'v': 1}]}
    jsonschema.validate(hint, schema=HINT_SCHEMA)
    bundle = HintBundle(vocabulary=vocab, hints=[hint])

    new_data = apply_hints(bundle, tmp_file)

    assert new_data == 'Foo bar baz'


def test_apply_hints_replacement_discarded_inside_deletion(tmp_file):
    """Test that a replacement is a no-op if happening inside a to-be-deleted fragment."""
    tmp_file.write_text('Foo bar baz')
    vocab = ['x']
    hint1 = {'p': [{'l': 5, 'r': 6, 'v': 0}]}  # replaces "a" with "x" in "bar"
    hint2 = {'p': [{'l': 4, 'r': 7}]}  # deletes "bar"
    hints = [hint1, hint2]
    for h in hints:
        jsonschema.validate(h, schema=HINT_SCHEMA)
    bundle = HintBundle(vocabulary=vocab, hints=hints)

    new_data = apply_hints(bundle, tmp_file)

    assert new_data == 'Foo  baz'


def test_apply_hints_replacement_discarded_inside_deletion(tmp_file):
    """Test that a deletion is a no-op if happening inside a to-be-replaced fragment."""
    tmp_file.write_text('Foo bar baz')
    vocab = ['some']
    hint1 = {'p': [{'l': 5, 'r': 6}]}  # deletes "a" in "bar"
    hint2 = {'p': [{'l': 4, 'r': 7, 'v': 0}]}  # replaces "bar" with "some"
    hints = [hint1, hint2]
    for h in hints:
        jsonschema.validate(h, schema=HINT_SCHEMA)
    bundle = HintBundle(vocabulary=vocab, hints=hints)

    new_data = apply_hints(bundle, tmp_file)

    assert new_data == 'Foo some baz'


def test_apply_hints_replacement_superseded_by_same_pos_deletion(tmp_file):
    """Test that a deletion takes precedence over a replacement in the same location."""
    tmp_file.write_text('Foo bar baz')
    vocab = ['x']
    hint1 = {'p': [{'l': 4, 'r': 5, 'v': 0}]}  # replaces "b" with "x" in "bar"
    hint2 = {'p': [{'l': 4, 'r': 7}]}  # deletes "bar"
    hints = [hint1, hint2]
    for h in hints:
        jsonschema.validate(h, schema=HINT_SCHEMA)
    bundle = HintBundle(vocabulary=vocab, hints=hints)

    new_data = apply_hints(bundle, tmp_file)

    assert new_data == 'Foo  baz'


def test_apply_hints_replacement_and_deletion_touching(tmp_file):
    """Test that deletions and replacements in touching, but not overlapping, fragments are applied independently."""
    tmp_file.write_text('Foo bar baz')
    vocab = ['some']
    hint1 = {'p': [{'l': 5, 'r': 7, 'v': 0}]}  # replaces "ar" with "some"
    hint2 = {'p': [{'l': 4, 'r': 5}]}  # deletes "b" in "bar"
    hint3 = {'p': [{'l': 7, 'r': 8}]}  # deletes " " after "bar"
    hints = [hint1, hint2, hint3]
    for h in hints:
        jsonschema.validate(h, schema=HINT_SCHEMA)
    bundle = HintBundle(vocabulary=vocab, hints=hints)

    new_data = apply_hints(bundle, tmp_file)

    assert new_data == 'Foo somebaz'


def test_apply_hints_overlapping_replacements(tmp_file):
    """Test overlapping replacements are handled gracefully.

    As there's no ideal solution for this kind of merge conflict, the main goal is to verify the implementation doesn't
    break. At the moment, the leftwise patch wins in this case, but this is subject to change in the future."""
    tmp_file.write_text('abcd')
    vocab = ['foo', 'x']
    hint1 = {'p': [{'l': 1, 'r': 3, 'v': 0}]}  # replaces "bc" with "foo"
    hint2 = {'p': [{'l': 2, 'r': 4, 'v': 1}]}  # replaces "cd" with "x"
    hints = [hint1, hint2]
    for h in hints:
        jsonschema.validate(h, schema=HINT_SCHEMA)
    bundle = HintBundle(vocabulary=vocab, hints=hints)

    new_data = apply_hints(bundle, tmp_file)

    assert new_data == 'afoo'


def test_store_load_hints(tmp_hints_file):
    vocab = ['new text']
    hint1 = {'p': [{'l': 0, 'r': 1}]}
    hint2 = {'p': [{'l': 2, 'r': 3}, {'l': 4, 'r': 5, 'v': 0}]}
    hints = HintBundle(vocabulary=vocab, hints=[hint1, hint2])
    store_hints(hints, tmp_hints_file)

    assert load_hints(tmp_hints_file, 0, 2) == HintBundle(vocabulary=vocab, hints=[hint1, hint2])
    assert load_hints(tmp_hints_file, 0, 1) == HintBundle(vocabulary=vocab, hints=[hint1])
    assert load_hints(tmp_hints_file, 1, 2) == HintBundle(vocabulary=vocab, hints=[hint2])


def test_hints_storage_compression(tmp_file):
    COUNT = 10000
    hints = [{'p': [{'l': i, 'r': i + 1}]} for i in range(COUNT)]
    bundle = HintBundle(hints=hints)
    store_hints(bundle, tmp_file)

    # Check that the file is significantly smaller than a regular JSON representation (without extra spaces around
    # separators).
    RATIO_AT_LEAST = 10
    hints_json_size = len(json.dumps(hints, separators=(',', ':')))
    assert tmp_file.stat().st_size * RATIO_AT_LEAST < hints_json_size

import json
import jsonschema
from pathlib import Path
import pytest

from cvise.utils.hint import apply_hints, HintBundle, load_hints, store_hints, HINT_SCHEMA


@pytest.fixture
def tmp_test_case(tmp_path: Path) -> Path:
    return tmp_path / 'file.txt'


@pytest.fixture
def tmp_transformed_file(tmp_path: Path) -> Path:
    return tmp_path / 'transformed.txt'


@pytest.fixture
def tmp_hints_file(tmp_path: Path) -> Path:
    return tmp_path / 'hints.zst'


def test_apply_hints_delete_prefix(tmp_test_case: Path, tmp_transformed_file: Path):
    tmp_test_case.write_text('Foo bar')
    hint = {'p': [{'l': 0, 'r': 4}]}
    jsonschema.validate(hint, schema=HINT_SCHEMA)
    bundle = HintBundle(hints=[hint])

    apply_hints([bundle], tmp_test_case, tmp_transformed_file)

    assert tmp_transformed_file.read_text() == 'bar'


def test_apply_hints_delete_suffix(tmp_test_case: Path, tmp_transformed_file: Path):
    tmp_test_case.write_text('Foo bar')
    hint = {'p': [{'l': 3, 'r': 7}]}
    jsonschema.validate(hint, schema=HINT_SCHEMA)
    bundle = HintBundle(hints=[hint])

    apply_hints([bundle], tmp_test_case, tmp_transformed_file)

    assert tmp_transformed_file.read_text() == 'Foo'


def test_apply_hints_delete_middle(tmp_test_case: Path, tmp_transformed_file: Path):
    tmp_test_case.write_text('Foo bar baz')
    hint = {'p': [{'l': 3, 'r': 7}]}
    jsonschema.validate(hint, schema=HINT_SCHEMA)
    bundle = HintBundle(hints=[hint])

    apply_hints([bundle], tmp_test_case, tmp_transformed_file)

    assert tmp_transformed_file.read_text() == 'Foo baz'


def test_apply_hints_delete_middle_multiple(tmp_test_case: Path, tmp_transformed_file: Path):
    tmp_test_case.write_text('Foo bar baz')
    hint1 = {'p': [{'l': 3, 'r': 4}]}
    hint2 = {'p': [{'l': 7, 'r': 8}]}
    hints = [hint1, hint2]
    for h in hints:
        jsonschema.validate(h, schema=HINT_SCHEMA)
    bundle = HintBundle(hints=hints)

    apply_hints([bundle], tmp_test_case, tmp_transformed_file)

    assert tmp_transformed_file.read_text() == 'Foobarbaz'


def test_apply_hints_delete_all(tmp_test_case: Path, tmp_transformed_file: Path):
    tmp_test_case.write_text('Foo bar')
    hint = {'p': [{'l': 0, 'r': 7}]}
    jsonschema.validate(hint, schema=HINT_SCHEMA)
    bundle = HintBundle(hints=[hint])

    apply_hints([bundle], tmp_test_case, tmp_transformed_file)

    assert tmp_transformed_file.read_text() == ''


def test_apply_hints_delete_touching(tmp_test_case: Path, tmp_transformed_file: Path):
    tmp_test_case.write_text('Foo bar baz')
    # It's essentially the deletion of [3..7).
    hint1 = {'p': [{'l': 3, 'r': 4}]}
    hint2 = {'p': [{'l': 6, 'r': 7}]}
    hint3 = {'p': [{'l': 5, 'r': 6}, {'l': 4, 'r': 5}]}
    hints = [hint1, hint2, hint3]
    for h in hints:
        jsonschema.validate(h, schema=HINT_SCHEMA)
    bundle = HintBundle(hints=hints)

    apply_hints([bundle], tmp_test_case, tmp_transformed_file)

    assert tmp_transformed_file.read_text() == 'Foo baz'


def test_apply_hints_delete_overlapping(tmp_test_case: Path, tmp_transformed_file: Path):
    tmp_test_case.write_text('Foo bar baz')
    # It's essentially the deletion of [3..7).
    hint1 = {'p': [{'l': 3, 'r': 6}]}
    hint2 = {'p': [{'l': 4, 'r': 7}]}
    hints = [hint1, hint2]
    for h in hints:
        jsonschema.validate(h, schema=HINT_SCHEMA)
    bundle = HintBundle(hints=hints)

    apply_hints([bundle], tmp_test_case, tmp_transformed_file)

    assert tmp_transformed_file.read_text() == 'Foo baz'


def test_apply_hints_delete_nested(tmp_test_case: Path, tmp_transformed_file: Path):
    tmp_test_case.write_text('Foo bar baz')
    hint1 = {'p': [{'l': 4, 'r': 6}]}
    hint2 = {'p': [{'l': 3, 'r': 7}]}
    hints = [hint1, hint2]
    for h in hints:
        jsonschema.validate(h, schema=HINT_SCHEMA)
    bundle = HintBundle(hints=hints)

    apply_hints([bundle], tmp_test_case, tmp_transformed_file)

    assert tmp_transformed_file.read_text() == 'Foo baz'


def test_apply_hints_replace_with_shorter(tmp_test_case: Path, tmp_transformed_file: Path):
    """Test a hint replacing a fragment with a shorter value."""
    tmp_test_case.write_text('Foo foobarbaz baz')
    vocab = ['xyz']
    hint = {'p': [{'l': 4, 'r': 13, 'v': 0}]}
    jsonschema.validate(hint, schema=HINT_SCHEMA)
    bundle = HintBundle(vocabulary=vocab, hints=[hint])

    apply_hints([bundle], tmp_test_case, tmp_transformed_file)

    assert tmp_transformed_file.read_text() == 'Foo xyz baz'


def test_apply_hints_replace_with_longer(tmp_test_case: Path, tmp_transformed_file: Path):
    """Test a hint replacing a fragment with a longer value."""
    tmp_test_case.write_text('Foo x baz')
    vocab = ['z', 'abacaba']
    hint = {'p': [{'l': 4, 'r': 5, 'v': 1}]}
    jsonschema.validate(hint, schema=HINT_SCHEMA)
    bundle = HintBundle(vocabulary=vocab, hints=[hint])

    apply_hints([bundle], tmp_test_case, tmp_transformed_file)

    assert tmp_transformed_file.read_text() == 'Foo abacaba baz'


def test_apply_hints_replacement_inside_deletion(tmp_test_case: Path, tmp_transformed_file: Path):
    """Test that a replacement is a no-op if happening inside a to-be-deleted fragment."""
    tmp_test_case.write_text('Foo bar baz')
    vocab = ['x']
    hint1 = {'p': [{'l': 5, 'r': 6, 'v': 0}]}  # replaces "a" with "x" in "bar"
    hint2 = {'p': [{'l': 4, 'r': 7}]}  # deletes "bar"
    hints = [hint1, hint2]
    for h in hints:
        jsonschema.validate(h, schema=HINT_SCHEMA)
    bundle = HintBundle(vocabulary=vocab, hints=hints)

    apply_hints([bundle], tmp_test_case, tmp_transformed_file)

    assert tmp_transformed_file.read_text() == 'Foo  baz'


def test_apply_hints_deletion_inside_replacement(tmp_test_case: Path, tmp_transformed_file: Path):
    """Test that a deletion is a no-op if happening inside a to-be-replaced fragment."""
    tmp_test_case.write_text('Foo bar baz')
    vocab = ['some']
    hint1 = {'p': [{'l': 5, 'r': 6}]}  # deletes "a" in "bar"
    hint2 = {'p': [{'l': 4, 'r': 7, 'v': 0}]}  # replaces "bar" with "some"
    hints = [hint1, hint2]
    for h in hints:
        jsonschema.validate(h, schema=HINT_SCHEMA)
    bundle = HintBundle(vocabulary=vocab, hints=hints)

    apply_hints([bundle], tmp_test_case, tmp_transformed_file)

    assert tmp_transformed_file.read_text() == 'Foo some baz'


def test_apply_hints_replacement_of_deleted_prefix(tmp_test_case: Path, tmp_transformed_file: Path):
    """Test that a deletion takes precedence over a replacement of the same substring's prefix.

    This covers the specific implementation detail of conflict resolution, beyond the simple rule "the leftmost hint
    wins in a group of overlapping hints" that'd suffice for other tests."""
    tmp_test_case.write_text('Foo bar baz')
    vocab = ['x']
    hint1 = {'p': [{'l': 4, 'r': 5, 'v': 0}]}  # replaces "b" with "x" in "bar"
    hint2 = {'p': [{'l': 4, 'r': 7}]}  # deletes "bar"
    hints = [hint1, hint2]
    for h in hints:
        jsonschema.validate(h, schema=HINT_SCHEMA)
    bundle = HintBundle(vocabulary=vocab, hints=hints)

    apply_hints([bundle], tmp_test_case, tmp_transformed_file)

    assert tmp_transformed_file.read_text() == 'Foo  baz'


def test_apply_hints_replacement_and_deletion_touching(tmp_test_case: Path, tmp_transformed_file: Path):
    """Test that deletions and replacements in touching, but not overlapping, fragments are applied independently."""
    tmp_test_case.write_text('Foo bar baz')
    vocab = ['some']
    hint1 = {'p': [{'l': 5, 'r': 7, 'v': 0}]}  # replaces "ar" with "some"
    hint2 = {'p': [{'l': 4, 'r': 5}]}  # deletes "b" in "bar"
    hint3 = {'p': [{'l': 7, 'r': 8}]}  # deletes " " after "bar"
    hints = [hint1, hint2, hint3]
    for h in hints:
        jsonschema.validate(h, schema=HINT_SCHEMA)
    bundle = HintBundle(vocabulary=vocab, hints=hints)

    apply_hints([bundle], tmp_test_case, tmp_transformed_file)

    assert tmp_transformed_file.read_text() == 'Foo somebaz'


def test_apply_hints_overlapping_replacements(tmp_test_case: Path, tmp_transformed_file: Path):
    """Test overlapping replacements are handled gracefully.

    As there's no ideal solution for this kind of merge conflict, the main goal is to verify the implementation doesn't
    break. At the moment, the leftwise patch wins in this case, but this is subject to change in the future."""
    tmp_test_case.write_text('abcd')
    vocab = ['foo', 'x']
    hint1 = {'p': [{'l': 1, 'r': 3, 'v': 0}]}  # replaces "bc" with "foo"
    hint2 = {'p': [{'l': 2, 'r': 4, 'v': 1}]}  # replaces "cd" with "x"
    hints = [hint1, hint2]
    for h in hints:
        jsonschema.validate(h, schema=HINT_SCHEMA)
    bundle = HintBundle(vocabulary=vocab, hints=hints)

    apply_hints([bundle], tmp_test_case, tmp_transformed_file)

    assert tmp_transformed_file.read_text() == 'afoo'


def test_apply_hints_multiple_bundles(tmp_test_case: Path, tmp_transformed_file: Path):
    tmp_test_case.write_text('foobar')
    hint02 = {'p': [{'l': 0, 'r': 2}]}
    hint13 = {'p': [{'l': 1, 'r': 3}]}
    hint24 = {'p': [{'l': 2, 'r': 4}]}
    hints = [hint02, hint13, hint24]
    for h in hints:
        jsonschema.validate(h, schema=HINT_SCHEMA)
    bundle1 = HintBundle(hints=[hint13])
    bundle2 = HintBundle(hints=[hint02, hint24])

    apply_hints([bundle1, bundle2], tmp_test_case, tmp_transformed_file)

    assert tmp_transformed_file.read_text() == 'ar'


def test_apply_hints_utf8(tmp_test_case: Path, tmp_transformed_file: Path):
    tmp_test_case.write_text('Brötchen 🍴')
    hint1 = {'p': [{'l': 0, 'r': 1}, {'l': 5, 'r': 7}]}
    hint2 = {'p': [{'l': 10, 'r': 14}]}
    hints = [hint1]
    for h in hints:
        jsonschema.validate(h, schema=HINT_SCHEMA)
    bundle1 = HintBundle(hints=[hint1])
    bundle2 = HintBundle(hints=[hint2])

    apply_hints([bundle1], tmp_test_case, tmp_transformed_file)
    assert tmp_transformed_file.read_text() == 'röten 🍴'
    apply_hints([bundle2], tmp_test_case, tmp_transformed_file)
    assert tmp_transformed_file.read_text() == 'Brötchen '


def test_apply_hints_non_unicode(tmp_test_case: Path, tmp_transformed_file: Path):
    tmp_test_case.write_bytes(b'\0F\xffoo')
    hint = {'p': [{'l': 2, 'r': 3}]}
    jsonschema.validate(hint, schema=HINT_SCHEMA)
    bundle = HintBundle(hints=[hint])

    apply_hints([bundle], tmp_test_case, tmp_transformed_file)

    assert tmp_transformed_file.read_bytes() == b'\0Foo'


def test_apply_hints_statistics(tmp_test_case: Path, tmp_transformed_file: Path):
    tmp_test_case.write_text('Foo bar baz')
    hint03 = {'p': [{'l': 0, 'r': 3}]}
    hint07 = {'p': [{'l': 0, 'r': 7}]}
    hint89 = {'p': [{'l': 8, 'r': 9}]}
    hints = [hint03, hint07, hint89]
    for h in hints:
        jsonschema.validate(h, schema=HINT_SCHEMA)
    bundle1 = HintBundle(hints=[hint03, hint89], pass_name='pass1')
    bundle2 = HintBundle(hints=[hint07], pass_name='pass2')

    stats = apply_hints([bundle1, bundle2], tmp_test_case, tmp_transformed_file)

    assert tmp_transformed_file.read_text() == ' az'
    assert stats.size_delta_per_pass == {'pass1': -1, 'pass2': -7}
    assert stats.get_passes_ordered_by_delta() == ['pass2', 'pass1']


def test_store_load_hints(tmp_hints_file):
    vocab = ['new text']
    hint1 = {'p': [{'l': 0, 'r': 1}]}
    hint2 = {'p': [{'l': 2, 'r': 3}, {'l': 4, 'r': 5, 'v': 0}]}
    hints = HintBundle(vocabulary=vocab, hints=[hint1, hint2])
    store_hints(hints, tmp_hints_file)

    assert load_hints(tmp_hints_file, 0, 2) == HintBundle(vocabulary=vocab, hints=[hint1, hint2])
    assert load_hints(tmp_hints_file, 0, 1) == HintBundle(vocabulary=vocab, hints=[hint1])
    assert load_hints(tmp_hints_file, 1, 2) == HintBundle(vocabulary=vocab, hints=[hint2])


def test_hints_storage_compression(tmp_hints_file: Path):
    COUNT = 10000
    hints = [{'p': [{'l': i, 'r': i + 1}]} for i in range(COUNT)]
    bundle = HintBundle(hints=hints)
    store_hints(bundle, tmp_hints_file)

    # Check that the file is significantly smaller than a regular JSON representation (without extra spaces around
    # separators).
    RATIO_AT_LEAST = 10
    hints_json_size = len(json.dumps(hints, separators=(',', ':')))
    assert tmp_hints_file.stat().st_size * RATIO_AT_LEAST < hints_json_size

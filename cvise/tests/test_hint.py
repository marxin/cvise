import msgspec
from pathlib import Path
import pytest

from cvise.utils.hint import apply_hints, Hint, HintBundle, load_hints, Patch, sort_hints, store_hints, subtract_hints
from cvise.tests.testabstract import validate_hint_bundle


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
    hint = Hint(patches=(Patch(left=0, right=4),))
    bundle = HintBundle(hints=[hint])
    validate_hint_bundle(bundle, tmp_test_case)

    apply_hints([bundle], tmp_test_case, tmp_transformed_file)

    assert tmp_transformed_file.read_text() == 'bar'


def test_apply_hints_delete_suffix(tmp_test_case: Path, tmp_transformed_file: Path):
    tmp_test_case.write_text('Foo bar')
    hint = Hint(patches=(Patch(left=3, right=7),))
    bundle = HintBundle(hints=[hint])
    validate_hint_bundle(bundle, tmp_test_case)

    apply_hints([bundle], tmp_test_case, tmp_transformed_file)

    assert tmp_transformed_file.read_text() == 'Foo'


def test_apply_hints_delete_middle(tmp_test_case: Path, tmp_transformed_file: Path):
    tmp_test_case.write_text('Foo bar baz')
    hint = Hint(patches=(Patch(left=3, right=7),))
    bundle = HintBundle(hints=[hint])
    validate_hint_bundle(bundle, tmp_test_case)

    apply_hints([bundle], tmp_test_case, tmp_transformed_file)

    assert tmp_transformed_file.read_text() == 'Foo baz'


def test_apply_hints_delete_middle_multiple(tmp_test_case: Path, tmp_transformed_file: Path):
    tmp_test_case.write_text('Foo bar baz')
    hint1 = Hint(patches=(Patch(left=3, right=4),))
    hint2 = Hint(patches=(Patch(left=7, right=8),))
    hints = [hint1, hint2]
    bundle = HintBundle(hints=hints)
    validate_hint_bundle(bundle, tmp_test_case)

    apply_hints([bundle], tmp_test_case, tmp_transformed_file)

    assert tmp_transformed_file.read_text() == 'Foobarbaz'


def test_apply_hints_delete_all(tmp_test_case: Path, tmp_transformed_file: Path):
    tmp_test_case.write_text('Foo bar')
    hint = Hint(patches=(Patch(left=0, right=7),))
    bundle = HintBundle(hints=[hint])
    validate_hint_bundle(bundle, tmp_test_case)

    apply_hints([bundle], tmp_test_case, tmp_transformed_file)

    assert tmp_transformed_file.read_text() == ''


def test_apply_hints_delete_touching(tmp_test_case: Path, tmp_transformed_file: Path):
    tmp_test_case.write_text('Foo bar baz')
    # It's essentially the deletion of [3..7).
    hint1 = Hint(patches=(Patch(left=3, right=4),))
    hint2 = Hint(patches=(Patch(left=6, right=7),))
    hint3 = Hint(
        patches=(
            Patch(left=5, right=6),
            Patch(left=4, right=5),
        )
    )
    hints = [hint1, hint2, hint3]
    bundle = HintBundle(hints=hints)
    validate_hint_bundle(bundle, tmp_test_case)

    apply_hints([bundle], tmp_test_case, tmp_transformed_file)

    assert tmp_transformed_file.read_text() == 'Foo baz'


def test_apply_hints_delete_overlapping(tmp_test_case: Path, tmp_transformed_file: Path):
    tmp_test_case.write_text('Foo bar baz')
    # It's essentially the deletion of [3..7).
    hint1 = Hint(patches=(Patch(left=3, right=6),))
    hint2 = Hint(patches=(Patch(left=4, right=7),))
    hints = [hint1, hint2]
    bundle = HintBundle(hints=hints)
    validate_hint_bundle(bundle, tmp_test_case)

    apply_hints([bundle], tmp_test_case, tmp_transformed_file)

    assert tmp_transformed_file.read_text() == 'Foo baz'


def test_apply_hints_delete_nested(tmp_test_case: Path, tmp_transformed_file: Path):
    tmp_test_case.write_text('Foo bar baz')
    hint1 = Hint(patches=(Patch(left=4, right=6),))
    hint2 = Hint(patches=(Patch(left=3, right=7),))
    hints = [hint1, hint2]
    bundle = HintBundle(hints=hints)
    validate_hint_bundle(bundle, tmp_test_case)

    apply_hints([bundle], tmp_test_case, tmp_transformed_file)

    assert tmp_transformed_file.read_text() == 'Foo baz'


def test_apply_hints_replace_with_shorter(tmp_test_case: Path, tmp_transformed_file: Path):
    """Test a hint replacing a fragment with a shorter value."""
    tmp_test_case.write_text('Foo foobarbaz baz')
    vocab = [b'xyz']
    hint = Hint(patches=(Patch(left=4, right=13, value=0),))
    bundle = HintBundle(vocabulary=vocab, hints=[hint])
    validate_hint_bundle(bundle, tmp_test_case)

    apply_hints([bundle], tmp_test_case, tmp_transformed_file)

    assert tmp_transformed_file.read_text() == 'Foo xyz baz'


def test_apply_hints_replace_with_longer(tmp_test_case: Path, tmp_transformed_file: Path):
    """Test a hint replacing a fragment with a longer value."""
    tmp_test_case.write_text('Foo x baz')
    vocab = [b'z', b'abacaba']
    hint = Hint(patches=(Patch(left=4, right=5, value=1),))
    bundle = HintBundle(vocabulary=vocab, hints=[hint])
    validate_hint_bundle(bundle, tmp_test_case)

    apply_hints([bundle], tmp_test_case, tmp_transformed_file)

    assert tmp_transformed_file.read_text() == 'Foo abacaba baz'


def test_apply_hints_replacement_inside_deletion(tmp_test_case: Path, tmp_transformed_file: Path):
    """Test that a replacement is a no-op if happening inside a to-be-deleted fragment."""
    tmp_test_case.write_text('Foo bar baz')
    vocab = [b'x']
    hint1 = Hint(patches=(Patch(left=5, right=6, value=0),))  # replaces "a" with "x" in "bar"
    hint2 = Hint(patches=(Patch(left=4, right=7),))  # deletes "bar"
    hints = [hint1, hint2]
    bundle = HintBundle(vocabulary=vocab, hints=hints)
    validate_hint_bundle(bundle, tmp_test_case)

    apply_hints([bundle], tmp_test_case, tmp_transformed_file)

    assert tmp_transformed_file.read_text() == 'Foo  baz'


def test_apply_hints_deletion_inside_replacement(tmp_test_case: Path, tmp_transformed_file: Path):
    """Test that a deletion is a no-op if happening inside a to-be-replaced fragment."""
    tmp_test_case.write_text('Foo bar baz')
    vocab = [b'some']
    hint1 = Hint(patches=(Patch(left=5, right=6),))  # deletes "a" in "bar"
    hint2 = Hint(patches=(Patch(left=4, right=7, value=0),))  # replaces "bar" with "some"
    hints = [hint1, hint2]
    bundle = HintBundle(vocabulary=vocab, hints=hints)
    validate_hint_bundle(bundle, tmp_test_case)

    apply_hints([bundle], tmp_test_case, tmp_transformed_file)

    assert tmp_transformed_file.read_text() == 'Foo some baz'


def test_apply_hints_replacement_of_deleted_prefix(tmp_test_case: Path, tmp_transformed_file: Path):
    """Test that a deletion takes precedence over a replacement of the same substring's prefix.

    This covers the specific implementation detail of conflict resolution, beyond the simple rule "the leftmost hint
    wins in a group of overlapping hints" that'd suffice for other tests."""
    tmp_test_case.write_text('Foo bar baz')
    vocab = [b'x']
    hint1 = Hint(patches=(Patch(left=4, right=5, value=0),))  # replaces "b" with "x" in "bar"
    hint2 = Hint(patches=(Patch(left=4, right=7),))  # deletes "bar"
    hints = [hint1, hint2]
    bundle = HintBundle(vocabulary=vocab, hints=hints)
    validate_hint_bundle(bundle, tmp_test_case)

    apply_hints([bundle], tmp_test_case, tmp_transformed_file)

    assert tmp_transformed_file.read_text() == 'Foo  baz'


def test_apply_hints_replacement_and_deletion_touching(tmp_test_case: Path, tmp_transformed_file: Path):
    """Test that deletions and replacements in touching, but not overlapping, fragments are applied independently."""
    tmp_test_case.write_text('Foo bar baz')
    vocab = [b'some']
    hint1 = Hint(patches=(Patch(left=5, right=7, value=0),))  # replaces "ar" with "some"
    hint2 = Hint(patches=(Patch(left=4, right=5),))  # deletes "b" in "bar"
    hint3 = Hint(patches=(Patch(left=7, right=8),))  # deletes " " after "bar"
    hints = [hint1, hint2, hint3]
    bundle = HintBundle(vocabulary=vocab, hints=hints)
    validate_hint_bundle(bundle, tmp_test_case)

    apply_hints([bundle], tmp_test_case, tmp_transformed_file)

    assert tmp_transformed_file.read_text() == 'Foo somebaz'


def test_apply_hints_overlapping_replacements(tmp_test_case: Path, tmp_transformed_file: Path):
    """Test overlapping replacements are handled gracefully.

    As there's no ideal solution for this kind of merge conflict, the main goal is to verify the implementation doesn't
    break. At the moment, the leftwise patch wins in this case, but this is subject to change in the future."""
    tmp_test_case.write_text('abcd')
    vocab = [b'foo', b'x']
    hint1 = Hint(patches=(Patch(left=1, right=3, value=0),))  # replaces "bc" with "foo"
    hint2 = Hint(patches=(Patch(left=2, right=4, value=1),))  # replaces "cd" with "x"
    hints = [hint1, hint2]
    bundle = HintBundle(vocabulary=vocab, hints=hints)
    validate_hint_bundle(bundle, tmp_test_case)

    apply_hints([bundle], tmp_test_case, tmp_transformed_file)

    assert tmp_transformed_file.read_text() == 'afoo'


def test_apply_hints_multiple_bundles(tmp_test_case: Path, tmp_transformed_file: Path):
    tmp_test_case.write_text('foobar')
    hint02 = Hint(patches=(Patch(left=0, right=2),))
    hint13 = Hint(patches=(Patch(left=1, right=3),))
    hint24 = Hint(patches=(Patch(left=2, right=4),))
    bundle1 = HintBundle(hints=[hint13])
    bundle2 = HintBundle(hints=[hint02, hint24])
    validate_hint_bundle(bundle1, tmp_test_case)
    validate_hint_bundle(bundle2, tmp_test_case)

    apply_hints([bundle1, bundle2], tmp_test_case, tmp_transformed_file)

    assert tmp_transformed_file.read_text() == 'ar'


def test_apply_hints_utf8(tmp_test_case: Path, tmp_transformed_file: Path):
    tmp_test_case.write_text('Brötchen 🍴')
    hint1 = Hint(
        patches=(
            Patch(left=0, right=1),
            Patch(left=5, right=7),
        )
    )
    hint2 = Hint(patches=(Patch(left=10, right=14),))
    bundle1 = HintBundle(hints=[hint1])
    bundle2 = HintBundle(hints=[hint2])
    validate_hint_bundle(bundle1, tmp_test_case)
    validate_hint_bundle(bundle2, tmp_test_case)

    apply_hints([bundle1], tmp_test_case, tmp_transformed_file)
    assert tmp_transformed_file.read_text() == 'röten 🍴'
    apply_hints([bundle2], tmp_test_case, tmp_transformed_file)
    assert tmp_transformed_file.read_text() == 'Brötchen '


def test_apply_hints_non_unicode(tmp_test_case: Path, tmp_transformed_file: Path):
    tmp_test_case.write_bytes(b'\0F\xffoo')
    hint = Hint(patches=(Patch(left=2, right=3),))
    bundle = HintBundle(hints=[hint])
    validate_hint_bundle(bundle, tmp_test_case)

    apply_hints([bundle], tmp_test_case, tmp_transformed_file)

    assert tmp_transformed_file.read_bytes() == b'\0Foo'


def test_apply_hints_dir(tmp_path: Path):
    """Test multi-file inputs."""
    input_dir = tmp_path / 'input'
    input_dir.mkdir()
    (input_dir / 'foo.h').write_text('unsigned foo;')
    (input_dir / 'bar.cc').write_text('void bar();')
    vocab = [b'foo.h', b'bar.cc']
    hint_oo = Hint(patches=(Patch(left=10, right=12, file=0),))
    hint_un = Hint(patches=(Patch(left=0, right=2, file=0),))
    hint_ar = Hint(patches=(Patch(left=6, right=8, file=1),))
    bundle = HintBundle(hints=[hint_oo, hint_un, hint_ar], vocabulary=vocab)
    validate_hint_bundle(bundle, input_dir, allowed_hint_types=set())

    output_dir = tmp_path / 'output'
    apply_hints([bundle], input_dir, output_dir)

    assert list(output_dir.glob('*')) == [output_dir / 'foo.h', output_dir / 'bar.cc']
    assert (output_dir / 'foo.h').read_text() == 'signed f;'
    assert (output_dir / 'bar.cc').read_text() == 'void b();'


def test_apply_hints_dir_nonexisting_parent(tmp_path: Path):
    """Test that an exception occurs when the destination path is in a non-existing directory.

    This behavior is important to avoid silently recreating already-deleted work directories of canceled jobs.
    """
    input_dir = tmp_path / 'input'
    input_dir.mkdir()
    (input_dir / 'foo.h').write_text('foo')
    (input_dir / 'bar.cc').write_text('void bar();')
    bundle = HintBundle(hints=[])
    validate_hint_bundle(bundle, tmp_test_case, allowed_hint_types=set())

    non_existing_dir = tmp_path / 'nonexisting'
    output_dir = non_existing_dir / 'output'
    with pytest.raises(FileNotFoundError):
        apply_hints([bundle], input_dir, output_dir)


def test_apply_hints_statistics(tmp_test_case: Path, tmp_transformed_file: Path):
    tmp_test_case.write_text('Foo bar baz')
    hint03 = Hint(patches=(Patch(left=0, right=3),))
    hint07 = Hint(patches=(Patch(left=0, right=7),))
    hint89 = Hint(patches=(Patch(left=8, right=9),))
    bundle1 = HintBundle(hints=[hint03, hint89], pass_name='pass1')
    bundle2 = HintBundle(hints=[hint07], pass_name='pass2')
    validate_hint_bundle(bundle1, tmp_test_case)
    validate_hint_bundle(bundle2, tmp_test_case)

    stats = apply_hints([bundle1, bundle2], tmp_test_case, tmp_transformed_file)

    assert tmp_transformed_file.read_text() == ' az'
    assert stats.size_delta_per_pass == {'pass1': -1, 'pass2': -7}
    assert stats.get_passes_ordered_by_delta() == ['pass2', 'pass1']


def test_store_load_hints(tmp_hints_file):
    vocab = [b'new text']
    hint1 = Hint(patches=(Patch(left=0, right=1),))
    hint2 = Hint(patches=(Patch(left=2, right=3), Patch(left=4, right=5, value=0)))
    hints = HintBundle(vocabulary=vocab, hints=[hint1, hint2])
    store_hints(hints, tmp_hints_file)

    assert load_hints(tmp_hints_file, 0, 2) == HintBundle(vocabulary=vocab, hints=[hint1, hint2])
    assert load_hints(tmp_hints_file, 0, 1) == HintBundle(vocabulary=vocab, hints=[hint1])
    assert load_hints(tmp_hints_file, 1, 2) == HintBundle(vocabulary=vocab, hints=[hint2])


def test_hints_storage_compression(tmp_hints_file: Path):
    COUNT = 10000
    hints = [Hint(patches=(Patch(left=i, right=i + 1),)) for i in range(COUNT)]
    bundle = HintBundle(hints=hints)
    store_hints(bundle, tmp_hints_file)

    # Check that the file is significantly smaller than a regular JSON representation (without extra spaces around
    # separators).
    RATIO_AT_LEAST = 10
    hints_json_size = len(msgspec.json.encode(hints))
    assert tmp_hints_file.stat().st_size * RATIO_AT_LEAST < hints_json_size


def test_subtract_hints():
    # Assume the text is 'foo bar x yz'.
    hint_foo = Hint(patches=(Patch(left=0, right=3),))
    hint_bar = Hint(patches=(Patch(left=4, right=7),))
    hint_x = Hint(patches=(Patch(left=8, right=9),))
    hint_yz = Hint(patches=(Patch(left=10, right=12),))
    bundle = HintBundle(hints=[hint_foo, hint_bar, hint_x, hint_yz])
    hint_o = Hint(patches=(Patch(left=2, right=3),))
    hint_oo = Hint(patches=(Patch(left=1, right=3),))
    hint_y = Hint(patches=(Patch(left=10, right=11),))
    bundle_to_apply = HintBundle(hints=[hint_o, hint_oo, hint_x, hint_y])

    got = subtract_hints(bundle, [bundle_to_apply])
    # the new text is 'f bar  y'
    hint2_f = Hint(patches=(Patch(left=0, right=1),))  # "foo" got cut to "f"
    hint2_bar = Hint(patches=(Patch(left=2, right=5),))  # "bar" moved left
    hint2_empty = Hint()
    hint2_z = Hint(patches=(Patch(left=7, right=8),))  # "yz" got cut to "z"
    assert got.hints == [hint2_f, hint2_bar, hint2_empty, hint2_z]


def test_subtract_hints_multifile():
    hint_file_a_03 = Hint(patches=(Patch(left=0, right=3, file=0),))
    hint_file_a_24 = Hint(patches=(Patch(left=2, right=4, file=0),), type=2)
    hint_file_b_24 = Hint(patches=(Patch(left=2, right=4, file=1),))
    hint_file_c_24 = Hint(patches=(Patch(left=2, right=4, file=3),), extra=4)
    bundle = HintBundle(
        hints=[hint_file_a_03, hint_file_a_24, hint_file_b_24, hint_file_c_24],
        vocabulary=[b'file_a', b'file_b', b'sometype', b'file_c', b'someextra'],
    )
    hint_file_b_05rm = Hint(patches=(Patch(left=0, right=5, file=0, operation=1),))
    bundle_to_apply_1 = HintBundle(hints=[hint_file_b_05rm], vocabulary=[b'file_b', b'rm'])
    hint_file_a_23 = Hint(patches=(Patch(left=2, right=3, file=1),))
    bundle_to_apply_2 = HintBundle(hints=[hint_file_a_23], vocabulary=[b'unused', b'file_a'])

    got = subtract_hints(bundle, [bundle_to_apply_1, bundle_to_apply_2])
    hint_file_a_02 = Hint(patches=(Patch(left=0, right=2, file=0),))
    hint_file_a_23 = Hint(patches=(Patch(left=2, right=3, file=0),), type=2)
    hint_empty = Hint()
    assert got.hints == [hint_file_a_02, hint_file_a_23, hint_empty, hint_file_c_24]
    assert got.vocabulary == bundle.vocabulary


def test_sort(tmp_test_case: Path):
    tmp_test_case.write_text('abcdefgh')
    hint0 = Hint(patches=(Patch(left=5, right=6), Patch(left=1, right=2)))
    hint1 = Hint(patches=(Patch(left=1, right=2, value=0),))
    hint2 = Hint(patches=(Patch(left=1, right=2, value=1), Patch(left=3, right=4)))
    hint3 = Hint(patches=(Patch(left=0, right=3),))
    bundle = HintBundle(vocabulary=[b'foo', b'bar', b''], hints=[hint0, hint1, hint2, hint3])
    validate_hint_bundle(bundle, tmp_test_case)
    sort_hints(bundle)

    hint0_new = Hint(patches=(Patch(left=1, right=2), Patch(left=5, right=6)))
    assert bundle.hints == [hint3, hint0_new, hint1, hint2]
    validate_hint_bundle(bundle, tmp_test_case)


def test_sort_multifile(tmp_test_case: Path):
    tmp_test_case.mkdir()
    (tmp_test_case / 'bar.txt').write_text('bar')
    (tmp_test_case / 'foo.txt').write_text('foo')
    hint0 = Hint(patches=(Patch(left=1, right=2, file=0),))
    hint1 = Hint(patches=(Patch(left=0, right=2, file=1),))
    hint2 = Hint(patches=(Patch(left=0, right=2, file=0, operation=2),))
    bundle = HintBundle(vocabulary=[b'bar.txt', b'foo.txt', b'rm'], hints=[hint0, hint1, hint2])
    validate_hint_bundle(bundle, tmp_test_case)
    sort_hints(bundle)

    assert bundle.hints == [hint2, hint0, hint1]
    validate_hint_bundle(bundle, tmp_test_case)

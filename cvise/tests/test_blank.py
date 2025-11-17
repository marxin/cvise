from pathlib import Path

import pytest

from cvise.passes.blank import BlankPass
from cvise.passes.hint_based import HintState
from cvise.tests.testabstract import collect_all_transforms, collect_all_transforms_dir, validate_stored_hints
from cvise.utils.process import ProcessEventNotifier


@pytest.fixture
def input_path(tmp_path: Path) -> Path:
    return tmp_path / 'input.txt'


def init_pass(tmp_dir: Path, input_path: Path) -> tuple[BlankPass, HintState | None]:
    pass_ = BlankPass()
    state = pass_.new(input_path, tmp_dir=tmp_dir, process_event_notifier=ProcessEventNotifier(None), dependee_hints=[])
    validate_stored_hints(state, pass_, input_path)
    return pass_, state


def test_empty_lines_removal(tmp_path: Path, input_path: Path):
    input_path.write_text('\n\nabc\n\n\ndef\n\n')
    p, state = init_pass(tmp_path, input_path)
    all_transforms = collect_all_transforms(p, state, input_path)

    assert b'abc\ndef\n' in all_transforms


def test_whitespace_only_lines_removal(tmp_path: Path, input_path: Path):
    input_path.write_text('   \n abc \n   \n ')
    p, state = init_pass(tmp_path, input_path)
    all_transforms = collect_all_transforms(p, state, input_path)

    assert b' abc \n' in all_transforms


def test_hash_lines_removal(tmp_path: Path, input_path: Path):
    input_path.write_text('# foo\nbar#1\n')
    p, state = init_pass(tmp_path, input_path)
    all_transforms = collect_all_transforms(p, state, input_path)

    assert b'bar#1\n' in all_transforms


def test_no_different_type_removals(tmp_path: Path, input_path: Path):
    """Verify that a single transform never attempts both empty line and hash-line removals.

    We want these two types of removals to be treated separately because their success rates may be very different, and
    it can be very ineffective to mix them in reduction attempts.
    """
    input_path.write_text('#x\n\n#y\nz\n')
    p, state = init_pass(tmp_path, input_path)
    all_transforms = collect_all_transforms(p, state, input_path)

    assert b'#x\n#y\nz\n' in all_transforms  # removal of empty lines
    assert b'\nz\n' in all_transforms  # removal of hash-lines
    assert b'z\n' not in all_transforms  # no removal of both


def test_non_utf8(tmp_path: Path, input_path: Path):
    input_path.write_bytes(
        b"""
        // \xff

        // \xee
        """,
    )
    p, state = init_pass(tmp_path, input_path)
    all_transforms = collect_all_transforms(p, state, input_path)

    assert (
        b"""
        // \xff
        // \xee
        """
        in all_transforms
    )


def test_dir_test_case(tmp_path: Path):
    input_dir = tmp_path / 'test_case'
    input_dir.mkdir()
    (input_dir / 'bar.h').write_text('int\n\nx;\n')
    (input_dir / 'foo.cc').write_text('void f()\n \n{}\n')
    p, state = init_pass(tmp_path, input_dir)
    all_transforms = collect_all_transforms_dir(p, state, input_dir)

    assert (('bar.h', b'int\nx;\n'), ('foo.cc', b'void f()\n{}\n')) in all_transforms

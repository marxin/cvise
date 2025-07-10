from pathlib import Path
import pytest
from typing import Tuple, Union

from cvise.passes.hint_based import HintState
from cvise.passes.blank import BlankPass
from cvise.tests.testabstract import collect_all_transforms


@pytest.fixture
def input_path(tmp_path: Path) -> Path:
    return tmp_path / 'input.txt'


def init_pass(tmp_dir: Path, input_path: Path) -> Tuple[BlankPass, Union[HintState, None]]:
    pass_ = BlankPass()
    state = pass_.new(input_path, tmp_dir=tmp_dir)
    return pass_, state


def test_empty_lines_removal(tmp_path: Path, input_path: Path):
    input_path.write_text('\n\nabc\n\n\ndef\n\n')
    p, state = init_pass(tmp_path, input_path)
    all_transforms = collect_all_transforms(p, state, input_path)

    assert 'abc\ndef\n' in all_transforms


def test_whitespace_only_lines_removal(tmp_path: Path, input_path: Path):
    input_path.write_text('   \n abc \n   \n ')
    p, state = init_pass(tmp_path, input_path)
    all_transforms = collect_all_transforms(p, state, input_path)

    assert ' abc \n' in all_transforms


def test_hash_lines_removal(tmp_path: Path, input_path: Path):
    input_path.write_text('# foo\nbar#1\n')
    p, state = init_pass(tmp_path, input_path)
    all_transforms = collect_all_transforms(p, state, input_path)

    assert 'bar#1\n' in all_transforms

from pathlib import Path
import pytest

from cvise.utils.fileutil import (
    chdir,
    copy_test_case,
    get_file_size,
    get_line_count,
    mkdir_up_to,
    replace_test_case_atomically,
)


def test_mkdir(tmp_path: Path):
    p = tmp_path / 'some' / 'path'
    mkdir_up_to(p, tmp_path)
    assert p.is_dir()


def test_mkdir_failure(tmp_path: Path):
    parent = tmp_path / 'some'
    p = parent / 'path'
    with pytest.raises(FileNotFoundError):
        mkdir_up_to(p, parent)


def test_get_file_size(tmp_path: Path):
    p = tmp_path / 'a.txt'
    p.write_text('foo')
    assert get_file_size(p) == 3


def test_get_line_count(tmp_path: Path):
    p = tmp_path / 'a.txt'
    p.write_text('foo\nbar\n')
    assert get_line_count(p) == 2


def test_copy(tmp_path: Path):
    work_dir = tmp_path / 'workdir'
    work_dir.mkdir()
    test_case = Path('a.txt')
    (work_dir / test_case).write_text('foo')
    target_dir = tmp_path / 'targetdir'
    target_dir.mkdir()

    with chdir(work_dir):
        copy_test_case(test_case, target_dir)

    assert (target_dir / test_case).read_text() == 'foo'


def test_copy_failure_nonexisting_destination(tmp_path: Path):
    work_dir = tmp_path / 'workdir'
    work_dir.mkdir()
    test_case = Path('a.txt')
    (work_dir / test_case).write_text('foo')
    target_dir = tmp_path / 'targetdir'
    # note no mkdir() for target_dir

    with chdir(work_dir):
        with pytest.raises(FileNotFoundError):
            copy_test_case(test_case, target_dir)


def test_replace(tmp_path: Path):
    work_dir = tmp_path / 'workdir'
    work_dir.mkdir()
    test_case = Path('a.txt')
    (work_dir / test_case).write_text('foo')
    new_dir = tmp_path / 'newdir'
    new_dir.mkdir()
    (new_dir / test_case).write_text('bar')

    with chdir(work_dir):
        replace_test_case_atomically(new_dir / test_case, test_case)

    assert (work_dir / test_case).read_text() == 'bar'
    assert len(list(new_dir.iterdir())) == 0  # the file got moved (which is O(1) within the same file system)
    assert len(list(work_dir.iterdir())) == 1  # no leftover temp files

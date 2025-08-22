from contextlib import contextmanager
import os
from pathlib import Path
import shutil
import tempfile
from typing import Iterator


# TODO: use tempfile.NamedTemporaryFile(delete_on_close=False) since Python 3.12 is the oldest supported release
@contextmanager
def CloseableTemporaryFile(mode='w+b', dir=None):
    f = tempfile.NamedTemporaryFile(mode=mode, delete=False, dir=dir)
    try:
        yield f
    finally:
        # For Windows systems, be sure we always close the file before we remove it!
        if not f.closed:
            f.close()
        try:
            os.remove(f.name)
        except FileNotFoundError:
            pass  # already deleted


# TODO: use contextlib.chdir once Python 3.11 is the oldest supported release
@contextmanager
def chdir(path: Path) -> Iterator[None]:
    original_workdir = os.getcwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(original_workdir)


def rmfolder(name):
    assert 'cvise' in str(name)
    try:
        shutil.rmtree(name)
    except OSError:
        pass


def mkdir_up_to(dir_to_create: Path, last_parent_dir: Path) -> None:
    """Similar to Path.mkdir(parents=True), but stops at the given ancestor directory which must exist.

    We use it to avoid canceled-but-not-killed-yet C-Vise jobs recreating temporary work directories that the C-Vise
    main process has deleted.
    """
    if dir_to_create == last_parent_dir or not dir_to_create.is_relative_to(last_parent_dir):
        return
    mkdir_up_to(dir_to_create.parent, last_parent_dir)
    dir_to_create.mkdir(exist_ok=True)


def get_file_size(test_case: Path) -> int:
    return test_case.stat().st_size


def get_line_count(test_case: Path) -> int:
    with open(test_case, 'rb') as f:
        return sum(1 for line in f if line and not line.isspace())


def copy_test_case(source: Path, destination_parent: Path) -> None:
    assert not source.is_absolute()
    mkdir_up_to(destination_parent / source.parent, destination_parent)
    shutil.copy2(source, destination_parent / source)


def replace_test_case_atomically(source: Path, destination: Path) -> None:
    with CloseableTemporaryFile(dir=destination.parent) as tmp:
        tmp_path = Path(tmp.name)
        tmp.close()
        shutil.move(source, tmp_path)
        tmp_path.rename(destination)

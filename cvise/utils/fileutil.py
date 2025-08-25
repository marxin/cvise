import contextlib
import os
from pathlib import Path
import random
import shutil
import string
import tempfile
from typing import Callable, Iterator


# TODO: use tempfile.NamedTemporaryFile(delete_on_close=False) since Python 3.12 is the oldest supported release
@contextlib.contextmanager
def CloseableTemporaryFile(mode='w+b', dir: Path = None):
    if dir is None:
        dir = Path(tempfile.gettempdir())
    # Use a unique name pattern, so that if NamedTemporaryFile construction or cleanup aborted mid-way (e.g., via
    # KeyboardInterrupt), we can identify and delete the leftover file.
    prefix = _get_random_temp_file_name_prefix()
    with _cleanup_on_abnormal_exit(lambda: _unlink_with_prefix(dir, prefix)):
        f = tempfile.NamedTemporaryFile(mode=mode, delete=False, dir=dir, prefix=prefix)
        with _auto_close_and_unlink(f):
            yield f


# TODO: use contextlib.chdir once Python 3.11 is the oldest supported release
@contextlib.contextmanager
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
    # First prepare the contents in a temporary file in the same folder as the destination path, and then rename the
    # temp file. The latter is atomic on popular file systems, while the former isn't since file system boundaries might
    # be crossed.
    with CloseableTemporaryFile(dir=destination.parent) as tmp:
        tmp_path = Path(tmp.name)
        tmp.close()
        shutil.move(source, tmp_path)
        tmp_path.rename(destination)


def _get_random_temp_file_name_prefix() -> str:
    LEN = 6
    letters = random.choices(string.ascii_uppercase + string.digits, k=LEN)
    return f'cvise-{"".join(letters)}-'


@contextlib.contextmanager
def _cleanup_on_abnormal_exit(func: Callable) -> Iterator[None]:
    try:
        yield
    except (KeyboardInterrupt, SystemExit):
        func()
        raise


@contextlib.contextmanager
def _auto_close_and_unlink(f: tempfile.NamedTemporaryFile) -> Iterator[None]:
    try:
        yield
    finally:
        # For Windows systems, be sure we always close the file before we remove it!
        if not f.closed:
            f.close()
        with contextlib.suppress(FileNotFoundError):
            os.unlink(f.name)


def _unlink_with_prefix(dir: Path, prefix: str) -> None:
    lst = list(dir.glob(f'{prefix}*'))
    for p in lst:
        if p.is_file():
            p.unlink(missing_ok=True)

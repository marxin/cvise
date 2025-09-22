import contextlib
import hashlib
import os
from pathlib import Path
import random
import shutil
import string
import tempfile
from typing import Iterable, Iterator, Union


# TODO: use tempfile.NamedTemporaryFile(delete_on_close=False) since Python 3.12 is the oldest supported release
@contextlib.contextmanager
def CloseableTemporaryFile(mode='w+b', dir: Union[Path, None] = None):
    if dir is None:
        dir = Path(tempfile.gettempdir())
    # Use a unique name pattern, so that if NamedTemporaryFile construction or cleanup aborted mid-way (e.g., via
    # KeyboardInterrupt), we can identify and delete the leftover file.
    prefix = _get_random_temp_file_name_prefix()
    with _clean_up_files_on_abnormal_exit(dir, prefix):
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
    return sum(p.stat().st_size for p in _get_test_case_files(test_case))


def get_line_count(test_case: Path) -> int:
    lines = 0
    for path in _get_test_case_files(test_case):
        with open(path, 'rb') as f:
            lines += sum(1 for line in f if line and not line.isspace())
    return lines


def copy_test_case(source: Path, destination_parent: Path) -> None:
    assert not source.is_absolute()
    mkdir_up_to(destination_parent / source.parent, destination_parent)
    if source.is_dir():
        shutil.copytree(source, destination_parent / source)
    else:
        shutil.copy2(source, destination_parent / source)


def replace_test_case_atomically(source: Path, destination: Path, move: bool = True) -> None:
    # First prepare the contents in a temporary location in the same folder as the destination path, and then rename/swap
    # it with the destination. We use the fact that a rename is atomic on popular file systems, within a single file
    # system's boundaries.
    if source.is_dir():
        with _robust_temp_dir(dir=destination.parent) as tmp_dir:
            tmp_path = Path(tmp_dir)

            new_path = tmp_path / source.name
            if move:
                shutil.move(source, new_path)
            else:
                shutil.copytree(source, new_path)

            old_destination = Path(f'{new_path}tmp')
            try:
                destination.rename(old_destination)
                new_path.rename(destination)
            except (KeyboardInterrupt, SystemExit):
                # If swapping was interrupted, attempt to bring back the original directory.
                with contextlib.suppress(Exception):
                    old_destination.rename(destination)
                raise
    else:
        with CloseableTemporaryFile(dir=destination.parent) as tmp:
            tmp_path = Path(tmp.name)
            tmp.close()
            if move:
                shutil.move(source, tmp_path)
            else:
                shutil.copy2(source, tmp_path)
            tmp_path.rename(destination)


def hash_test_case(test_case: Path) -> bytes:
    with open(test_case, 'rb', buffering=0) as f:
        return hashlib.file_digest(f, 'sha256').digest()


def _get_test_case_files(test_case: Path) -> Iterable[Path]:
    if test_case.is_dir():
        return [p for p in test_case.rglob('*') if p.is_file() and not p.is_symlink()]
    return [test_case]


def _get_random_temp_file_name_prefix() -> str:
    LEN = 6
    letters = random.choices(string.ascii_uppercase + string.digits, k=LEN)
    return f'cvise-{"".join(letters)}-'


@contextlib.contextmanager
def _clean_up_files_on_abnormal_exit(dir: Path, prefix: str) -> Iterator[None]:
    try:
        yield
    except (KeyboardInterrupt, SystemExit):
        lst = list(dir.glob(f'{prefix}*'))
        for p in lst:
            if p.is_file():
                p.unlink(missing_ok=True)
            else:
                shutil.rmtree(p)
        raise


@contextlib.contextmanager
def _auto_close_and_unlink(tmp_file) -> Iterator[None]:
    try:
        yield
    finally:
        # For Windows systems, be sure we always close the file before we remove it!
        if not tmp_file.closed:
            tmp_file.close()
        with contextlib.suppress(FileNotFoundError):
            os.unlink(tmp_file.name)


@contextlib.contextmanager
def _robust_temp_dir(dir: Path) -> Iterator[Path]:
    """Unlike TemporaryDirectory, guarantees to not leave leftovers on keyboard/exit exceptions."""
    prefix = _get_random_temp_file_name_prefix()
    with _clean_up_files_on_abnormal_exit(dir, prefix):
        with tempfile.TemporaryDirectory(prefix=prefix, dir=dir) as tmp_dir:
            yield Path(tmp_dir)

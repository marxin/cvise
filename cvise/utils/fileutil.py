from __future__ import annotations

import contextlib
import difflib
import fnmatch
import hashlib
import io
import os
import random
import re
import shutil
import string
import tempfile
import threading
from collections.abc import Iterable, Iterator
from copy import copy
from pathlib import Path

# Singleton buffer for hash_test_case(), to avoid reallocations.
_hash_buf: bytearray | None = None


# TODO: use tempfile.NamedTemporaryFile(delete_on_close=False) since Python 3.12 is the oldest supported release
@contextlib.contextmanager
def CloseableTemporaryFile(mode='w+b', dir: Path | None = None):
    if dir is None:
        dir = Path(tempfile.gettempdir())
    # Use a unique name pattern, so that if NamedTemporaryFile construction or cleanup aborted mid-way (e.g., via
    # KeyboardInterrupt), we can identify and delete the leftover file.
    prefix = _get_random_temp_file_name_prefix()
    with _clean_up_files_on_abnormal_exit(dir, prefix):
        f = tempfile.NamedTemporaryFile(mode=mode, delete=False, dir=dir, prefix=prefix)
        with _auto_close_and_unlink(f):
            yield f


class TmpDirManager:
    TEMP_PREFIX = 'cvise-'
    JANITOR_INTERVAL = 10  # seconds
    _MAX_RETRIES = 10000
    _ALPHABET = string.ascii_letters + string.digits
    _RANDOM_LENGTH = 6

    def __init__(self, prefix=None, save_temps: bool = False):
        self._save_temps = save_temps
        self.root = Path(tempfile.mkdtemp(prefix=self.TEMP_PREFIX if prefix is None else prefix))
        self._lock = threading.Lock()
        self._dirs = set()
        self._janitor_thread = threading.Thread(target=self._janitor_thread_main)
        self._shutdown_event = threading.Event()

    def create_dir(self, prefix: str) -> Path:
        assert self.root is not None
        created = self._do_create_dir(prefix)
        assert created.relative_to(self.root)
        return created

    def delete_dir(self, dir: Path) -> None:
        assert dir in self._dirs
        if self._save_temps:
            return
        shutil.rmtree(dir, ignore_errors=True)  # the janitor thread will clean leftovers on error
        with self._lock:
            self._dirs.remove(dir)

    def __enter__(self) -> TmpDirManager:
        self._janitor_thread.start()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        assert self.root is not None
        self._shutdown_event.set()
        self._janitor_thread.join(timeout=600)  # semi-arbitrary timeout to prevent possibility of deadlocks
        if not self._save_temps:
            shutil.rmtree(
                self.root,
                ignore_errors=True,  # this is unfortunate, however skipping all other cleanup would likely be annoying
            )
        self._dirs.clear()
        self.root = None

    def _do_create_dir(self, prefix: str) -> Path:
        # We don't use tempfile.mkdtemp() because to prevent racing with the deletions by the janitor thread, we need to
        # put a candidate dir into _dirs before we create it.
        assert self.root is not None
        for attempt in range(self._MAX_RETRIES):
            # On the first attempt, try without adding suffixes, to reduce risk of hitting path length limits in C-Vise.
            suffix = '' if attempt == 0 else self._random_suffix()
            candidate = self.root / (prefix + suffix)
            if candidate.exists():
                continue

            with self._lock:
                if candidate in self._dirs:
                    continue
                self._dirs.add(candidate)

            try:
                candidate.mkdir(mode=0o700)
            except FileExistsError:
                pass
            else:
                return candidate

            with self._lock:
                self._dirs.remove(candidate)

        raise RuntimeError(
            f'Failed to create temporary directory under {self.root} with prefix "{prefix}" after {self._MAX_RETRIES}'
            + ' attempts'
        )

    def _random_suffix(self) -> str:
        return '-' + ''.join(random.choices(self._ALPHABET, k=self._RANDOM_LENGTH))

    def _janitor_thread_main(self) -> None:
        while not self._shutdown_event.is_set():
            with self._lock:
                present: set[Path] = set(self.root.iterdir())
                known: set[Path] = copy(self._dirs)

            to_delete = present - known
            for path in to_delete:
                if path.is_file():
                    path.unlink(missing_ok=True)
                else:
                    shutil.rmtree(path, ignore_errors=True)

            self._shutdown_event.wait(timeout=self.JANITOR_INTERVAL)


def sanitize_for_file_name(text: str) -> str:
    """Replaces characters which might be invalid or error-prone (e.g., spaces) when used in file names."""
    return re.sub(r'[^a-zA-Z0-9_.-]', '_', text)


def get_file_size(test_case: Path) -> int:
    return sum(p.stat().st_size for p in _get_test_case_files(test_case))


def get_line_count(test_case: Path) -> int:
    lines = 0
    for path in _get_test_case_files(test_case):
        with open(path, 'rb') as f:
            lines += sum(1 for line in f if line and not line.isspace())
    return lines


def get_file_count(test_case: Path) -> int:
    if not test_case.is_dir():
        return 1
    return sum(1 for p in test_case.rglob('*') if not p.is_dir())


def get_dir_count(test_case: Path) -> int:
    if not test_case.is_dir():
        return 0
    return 1 + sum(1 for p in test_case.rglob('*') if p.is_dir())


def copy_test_case(source: Path, destination_parent: Path) -> None:
    assert not source.is_absolute()
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
    # TODO: use hashlib.file_digest once Python 3.11 is the oldest supported release
    BUF_SIZE = 2**18

    global _hash_buf
    if _hash_buf is None:  # lazily initialize singleton
        _hash_buf = bytearray(BUF_SIZE)
    buf = _hash_buf  # cache in local variables, which are presumably faster

    buf_view = memoryview(buf)
    if test_case.is_dir():
        return _hash_dir_tree(test_case, buf_view)
    else:
        return _hash_file(test_case, buf_view)


def filter_files_by_patterns(test_case: Path, include_globs: list[str], default_exclude_globs: list[str]) -> list[Path]:
    if include_globs:
        paths = _find_files_matching(test_case, include_globs)
    else:
        all = _find_files_matching(test_case, ['**/*'])
        exclude = _find_files_matching(test_case, default_exclude_globs)
        paths = set(all) - set(exclude)
    return sorted(paths)


def diff_test_cases(orig_test_case: Path, changed_test_case: Path) -> bytes:
    rel_paths = []
    if orig_test_case.is_dir():
        orig_paths = {p.relative_to(orig_test_case) for p in orig_test_case.rglob('*')}
        dest_paths = {p.relative_to(changed_test_case) for p in changed_test_case.rglob('*')}
        rel_paths = sorted(orig_paths | dest_paths)
    else:
        rel_paths = [Path()]

    diff_lines: list[bytes] = []
    for rel_path in rel_paths:
        orig_path = orig_test_case / rel_path
        dest_path = changed_test_case / rel_path

        if orig_path.is_dir() or orig_path.is_symlink() or dest_path.is_dir() or dest_path.is_symlink():
            if not dest_path.exists():
                diff_lines.append(f'--- {orig_path}\n'.encode())
            elif not orig_path.exists():
                diff_lines.append(f'+++ {orig_path}\n'.encode())
            continue

        orig_data = _try_read_file_lines(orig_path)
        changed_data = _try_read_file_lines(dest_path)
        path_for_log = str(orig_path).encode()
        diff = list(difflib.diff_bytes(difflib.unified_diff, orig_data, changed_data, path_for_log, path_for_log))
        if not diff:
            continue
        if not diff[-1].endswith(b'\n'):
            diff[-1] += b'\n'
        diff_lines += diff
    return b''.join(diff_lines)


def remove_extraneous_files(test_case: Path, expected_paths: set[Path]) -> None:
    paths = sorted(test_case.rglob('*'), reverse=True)
    for path in paths:
        if path in expected_paths:
            continue
        if path.is_dir():
            path.rmdir()  # the reversed order guarantees the files should've been deleted
        else:
            path.unlink()


def _try_read_file_lines(path: Path) -> list[bytes]:
    if not path.is_file():
        return []
    with open(path, 'rb') as f:
        return f.readlines()


def _hash_file(path: Path, buf: memoryview) -> bytes:
    hash = hashlib.sha256()
    with io.FileIO(path, 'r') as f:  # use FileIO instead of open() as otherwise linters don't allow readinto()
        while read_size := f.readinto(buf):
            hash.update(buf[:read_size])
    return hash.digest()


def _hash_dir_tree(dir: Path, buf: memoryview) -> bytes:
    dir_hash = hashlib.sha256()
    descendants = sorted(dir.rglob('*'))
    for path in descendants:
        rel_path = str(path.relative_to(dir)).encode()
        path_hash = hashlib.sha256(rel_path).digest()
        dir_hash.update(path_hash)

        dir_hash.update(bytes([path.is_dir(), path.is_file(), path.is_symlink()]))

        if path.is_symlink():
            dest_path = str(Path(os.readlink(path))).encode()
            dest_path_hash = hashlib.sha256(dest_path).digest()
            dir_hash.update(dest_path_hash)
        elif path.is_file():
            dir_hash.update(_hash_file(path, buf))
    return dir_hash.digest()


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


def _find_files_matching(test_case: Path, globs: list[str]) -> list[Path]:
    if test_case.is_symlink():
        return []

    if not test_case.is_dir():
        # TODO: use full_match() once Python 3.13 is the oldest supported release
        for pattern in globs:
            pattern = pattern.removeprefix('**/')
            if fnmatch.fnmatch(str(test_case), pattern):
                return [test_case]
        return []

    inode_to_path = {}
    for pattern in globs:
        for path in test_case.glob(pattern):
            if not path.is_dir() and not path.is_symlink() and path.is_relative_to(test_case):
                st = path.stat()
                key = st.st_dev, st.st_ino
                inode_to_path.setdefault(key, path)
    return list(inode_to_path.values())

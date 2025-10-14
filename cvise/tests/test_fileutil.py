import contextlib
import enum
import os
from pathlib import Path
import pytest
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from typing import Callable, Union

from cvise.utils.fileutil import (
    chdir,
    copy_test_case,
    diff_test_cases,
    filter_files_by_patterns,
    get_file_size,
    get_line_count,
    hash_test_case,
    remove_extraneous_files,
    replace_test_case_atomically,
    sanitize_for_file_name,
)


@pytest.fixture
def input_in_source_dir():
    """Creates a test case directory next to our .py file.

    This is useful for tests that need a non-tmpfs location - e.g., atomicity tests which are much more comprehensive
    when file paths cross file system boundaries.
    """
    current = Path(__file__).parent.resolve()
    with tempfile.TemporaryDirectory(dir=current) as tmp_dir:
        yield Path(tmp_dir)


def test_sanitize():
    assert sanitize_for_file_name('Foo123') == 'Foo123'
    assert sanitize_for_file_name('foo bar') == 'foo_bar'
    assert sanitize_for_file_name('foo bar') == 'foo_bar'
    assert sanitize_for_file_name('example.txt') == 'example.txt'
    assert sanitize_for_file_name('@something') == '_something'
    assert sanitize_for_file_name('a-b') == 'a-b'
    assert sanitize_for_file_name('a_b') == 'a_b'


def test_get_file_size(tmp_path: Path):
    p = tmp_path / 'a.txt'
    p.write_text('foo')
    assert get_file_size(p) == 3


def test_get_file_size_dir(tmp_path: Path):
    (tmp_path / 'a.txt').write_text('foo')
    (tmp_path / 'b').mkdir()
    (tmp_path / 'b' / 'c.txt').write_text('foobar')
    assert get_file_size(tmp_path) == 9


def test_get_line_count(tmp_path: Path):
    p = tmp_path / 'a.txt'
    p.write_text('foo\nbar\n')
    assert get_line_count(p) == 2


def test_get_line_count_dir(tmp_path: Path):
    (tmp_path / 'a.txt').write_text('foo\nbar\n')
    (tmp_path / 'b').mkdir()
    (tmp_path / 'b' / 'c.txt').write_text('x\ny\nz')
    assert get_line_count(tmp_path) == 5


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


def test_copy_dir(tmp_path: Path):
    work_dir = tmp_path / 'workdir'
    work_dir.mkdir()
    test_case = Path('test')
    (work_dir / test_case).mkdir()
    (work_dir / test_case / 'a.txt').write_text('foo')
    (work_dir / test_case / 'b').mkdir()
    (work_dir / test_case / 'b' / 'c.txt').write_text('bar')

    target_dir = tmp_path / 'targetdir'
    target_dir.mkdir()

    with chdir(work_dir):
        copy_test_case(test_case, target_dir)

    assert (target_dir / 'test').is_dir()
    assert (target_dir / 'test' / 'a.txt').read_text() == 'foo'
    assert (target_dir / 'test' / 'b').is_dir()
    assert (target_dir / 'test' / 'b' / 'c.txt').read_text() == 'bar'


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


def test_replace_dir(tmp_path: Path):
    work_dir = tmp_path / 'workdir'
    work_dir.mkdir()
    test_case = Path('test')
    (work_dir / test_case).mkdir()
    (work_dir / test_case / 'a.txt').write_text('foo')
    (work_dir / test_case / 'b').mkdir()
    (work_dir / test_case / 'b' / 'c.txt').write_text('bar')

    new_dir = tmp_path / 'newdir'
    new_dir.mkdir()
    (new_dir / test_case).mkdir()
    (new_dir / test_case / 'a.txt').write_text('newfoo')
    (new_dir / test_case / 'd').mkdir()
    (new_dir / test_case / 'd' / 'd.txt').write_text('newbar')

    with chdir(work_dir):
        replace_test_case_atomically(new_dir / test_case, test_case)

    assert (work_dir / test_case / 'a.txt').read_text() == 'newfoo'
    assert (work_dir / test_case / 'd' / 'd.txt').read_text() == 'newbar'
    assert not (work_dir / test_case / 'b').exists()
    assert len(list(new_dir.iterdir())) == 0  # the dir got moved (which is O(1) within the same file system)
    assert len(list(work_dir.iterdir())) == 1  # no leftover temp files


class _AtomicityResult(enum.Enum):
    CONTENTS_INITIAL = 0
    CONTENTS_NEW = 1
    CONTENTS_UNEXPECTED = 2


def test_replace_file_atomicity(tmp_path: Path, input_in_source_dir: Path):
    """Verifies whether the file replacement operation is atomic.

    We do this by killing at "random" time points a child process that performs the file replacement.
    """
    INITIAL_DATA = 'a' * 1_000
    NEW_DATA = 'b' * 2_000

    # Not storing the source file in the tmp_path because to catch non-atomicity the source and the destination have to
    # be on different file systems.
    test_case = Path('a.txt')
    new_dir = tmp_path / 'newdir'
    new_dir.mkdir()

    def init() -> None:
        (input_in_source_dir / test_case).write_text(INITIAL_DATA)
        (new_dir / test_case).write_text(NEW_DATA)

    def check_result(contents: dict[Path, str]) -> _AtomicityResult:
        if contents == {test_case: INITIAL_DATA}:
            return _AtomicityResult.CONTENTS_INITIAL
        elif contents == {test_case: NEW_DATA}:
            return _AtomicityResult.CONTENTS_NEW
        else:
            return _AtomicityResult.CONTENTS_UNEXPECTED

    test_code = (
        'from cvise.utils.fileutil import replace_test_case_atomically; '
        + 'from os import chdir; '
        + 'from pathlib import Path; '
        + f'chdir("{input_in_source_dir}"); '
        + f'replace_test_case_atomically(Path("{new_dir / test_case}"), Path("{test_case}"));'
    )

    _stress_test_atomicity(input_in_source_dir, init, test_code, check_result)


def test_replace_dir_atomicity(tmp_path: Path, input_in_source_dir: Path):
    """Verifies whether the directory replacement operation is atomic."""
    INITIAL_DATA = 'a' * 1_000
    NEW_DATA = 'b' * 2_000

    # Not storing the source file in the tmp_path because to catch non-atomicity the source and the destination have to
    # be on different file systems.
    test_case = Path('test')
    new_dir = tmp_path / 'newdir'
    new_dir.mkdir()

    def init() -> None:
        shutil.rmtree(input_in_source_dir / test_case, ignore_errors=True)
        (input_in_source_dir / test_case).mkdir()
        (input_in_source_dir / test_case / 'a.txt').write_text(INITIAL_DATA)
        (input_in_source_dir / test_case / 'b').mkdir()
        (input_in_source_dir / test_case / 'b' / 'c.txt').write_text('')

        shutil.rmtree(new_dir / test_case, ignore_errors=True)
        (new_dir / test_case).mkdir()
        (new_dir / test_case / 'newa.txt').write_text(NEW_DATA)
        (new_dir / test_case / 'newb').mkdir()
        (new_dir / test_case / 'newb' / 'newc.txt').write_text('')

    def check_result(contents: dict[Path, str]) -> _AtomicityResult:
        if contents == {test_case / 'a.txt': INITIAL_DATA, test_case / 'b/c.txt': ''}:
            return _AtomicityResult.CONTENTS_INITIAL
        elif contents == {test_case / 'newa.txt': NEW_DATA, test_case / 'newb/newc.txt': ''}:
            return _AtomicityResult.CONTENTS_NEW
        else:
            return _AtomicityResult.CONTENTS_UNEXPECTED

    test_code = (
        'from cvise.utils.fileutil import replace_test_case_atomically; '
        + 'from os import chdir; '
        + 'from pathlib import Path; '
        + f'chdir("{input_in_source_dir}"); '
        + f'replace_test_case_atomically(Path("{new_dir / test_case}"), Path("{test_case}"));'
    )

    _stress_test_atomicity(input_in_source_dir, init, test_code, check_result)


def _stress_test_atomicity(path_to_check: Path, init_callback: Callable, test_code: str, result_callback: Callable):
    BINSEARCH_STEPS = 10
    RECHECK_ITERATIONS = 10
    TEST_HALVING_STEPS = 10

    def run_subprocess(sleep: Union[float, None]):
        init_callback()
        # Enable tracing in the subprocess in order to slow it down, to increase chances of hitting a bug.
        code = 'from sys import settrace; ' + 'trace = lambda *args: trace; ' + 'settrace(trace); ' + test_code

        proc = subprocess.Popen([sys.executable, '-c', code], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if sleep is not None:
            time.sleep(sleep)
            os.kill(proc.pid, signal.SIGINT)
        proc.wait()

        contents = {}
        for p in path_to_check.rglob('*'):
            with contextlib.suppress(FileNotFoundError):
                if p.is_file():
                    contents[p.relative_to(path_to_check)] = p.read_text()
        return contents

    begin_time = time.monotonic()
    assert result_callback(run_subprocess(sleep=None)) == _AtomicityResult.CONTENTS_NEW
    initial_duration = time.monotonic() - begin_time

    # Estimate using binary search the "critical" time - how long it takes for the code-under-test to start modifying
    # the input file.
    left = 0
    right = initial_duration
    for _ in range(BINSEARCH_STEPS):
        mid = (left + right) / 2
        all_initial = True
        for _ in range(RECHECK_ITERATIONS):
            contents = run_subprocess(mid)
            assert result_callback(contents) != _AtomicityResult.CONTENTS_UNEXPECTED
            if result_callback(contents) == _AtomicityResult.CONTENTS_NEW:
                all_initial = False
                break
        if all_initial:
            left = mid
        else:
            right = mid
    critical_time = left

    # Test the atomicity by trying to kill the process at various times around the critical time.
    for i in range(TEST_HALVING_STEPS):
        step = critical_time / 2**i
        for j in range(min(TEST_HALVING_STEPS, i + 1)):
            assert result_callback(run_subprocess(critical_time + step * j)) != _AtomicityResult.CONTENTS_UNEXPECTED
            assert result_callback(run_subprocess(critical_time - step * j)) != _AtomicityResult.CONTENTS_UNEXPECTED


def test_hash_equality_file(tmp_path: Path):
    path_a = tmp_path / 'a.txt'
    path_a.write_text('foo')
    path_b = tmp_path / 'b.txt'
    path_b.write_text('foo')
    path_c = tmp_path / 'c.txt'
    path_c.write_text('bar')

    assert hash_test_case(path_a) == hash_test_case(path_b)
    assert hash_test_case(path_a) != hash_test_case(path_c)


def test_hash_empty_file(tmp_path: Path):
    path_a = tmp_path / 'a.txt'
    path_a.touch()
    path_b = tmp_path / 'b.txt'
    path_b.touch()

    assert hash_test_case(path_a) == hash_test_case(path_b)


def test_hash_dir_same_files(tmp_path: Path):
    dir_a = tmp_path / 'a'
    dir_a.mkdir()
    (dir_a / 'foo.txt').write_text('foo')
    dir_b = tmp_path / 'b'
    dir_b.mkdir()
    (dir_b / 'foo.txt').write_text('foo')

    assert hash_test_case(dir_a) == hash_test_case(dir_b)


def test_hash_dir_different_file_paths(tmp_path: Path):
    dir_a = tmp_path / 'a'
    dir_a.mkdir()
    (dir_a / 'foo.txt').write_text('foo')
    dir_b = tmp_path / 'b'
    dir_b.mkdir()
    (dir_b / 'bar.txt').write_text('foo')

    assert hash_test_case(dir_a) != hash_test_case(dir_b)


def test_hash_dir_different_file_contents(tmp_path: Path):
    dir_a = tmp_path / 'a'
    dir_a.mkdir()
    (dir_a / 'foo.txt').write_text('foo')
    dir_b = tmp_path / 'b'
    dir_b.mkdir()
    (dir_b / 'foo.txt').write_text('bar')

    assert hash_test_case(dir_a) != hash_test_case(dir_b)


def test_hash_dir_same_subdirs(tmp_path: Path):
    dir_a = tmp_path / 'a'
    dir_a.mkdir()
    (dir_a / 'foo').mkdir()
    dir_b = tmp_path / 'b'
    dir_b.mkdir()
    (dir_b / 'foo').mkdir()

    assert hash_test_case(dir_a) == hash_test_case(dir_b)


def test_hash_dir_different_subdirs(tmp_path: Path):
    dir_a = tmp_path / 'a'
    dir_a.mkdir()
    (dir_a / 'foo').mkdir()
    dir_b = tmp_path / 'b'
    dir_b.mkdir()
    (dir_b / 'bar').mkdir()

    assert hash_test_case(dir_a) != hash_test_case(dir_b)


def test_hash_dir_same_symlinks(tmp_path: Path):
    dir_a = tmp_path / 'a'
    dir_a.mkdir()
    (dir_a / 'foo').symlink_to('bar')
    dir_b = tmp_path / 'b'
    dir_b.mkdir()
    (dir_b / 'foo').symlink_to('bar')

    assert hash_test_case(dir_a) == hash_test_case(dir_b)


def test_hash_dir_different_symlinks(tmp_path: Path):
    dir_a = tmp_path / 'a'
    dir_a.mkdir()
    (dir_a / 'foo').symlink_to('bar')
    dir_b = tmp_path / 'b'
    dir_b.mkdir()
    (dir_b / 'foo').symlink_to('barbaz')

    assert hash_test_case(dir_a) != hash_test_case(dir_b)


def test_filter_files(tmp_path: Path):
    p = tmp_path
    (p / 'bar.c').touch()
    (p / 'foo.cc').touch()
    (p / 'foo.h').touch()
    (p / 'Makefile').touch()
    (p / 'dir').mkdir()
    (p / 'dir' / 'a.c').touch()

    assert filter_files_by_patterns(p, include_globs=[], default_exclude_globs=[]) == [
        p / 'Makefile',
        p / 'bar.c',
        p / 'dir' / 'a.c',
        p / 'foo.cc',
        p / 'foo.h',
    ]
    assert filter_files_by_patterns(p, include_globs=['**/*'], default_exclude_globs=[]) == [
        p / 'Makefile',
        p / 'bar.c',
        p / 'dir' / 'a.c',
        p / 'foo.cc',
        p / 'foo.h',
    ]
    assert filter_files_by_patterns(p, include_globs=['**/Makefile'], default_exclude_globs=[]) == [
        p / 'Makefile',
    ]
    assert filter_files_by_patterns(p, include_globs=['*.c'], default_exclude_globs=[]) == [
        p / 'bar.c',
    ]
    assert filter_files_by_patterns(p, include_globs=['**/*.c'], default_exclude_globs=[]) == [
        p / 'bar.c',
        p / 'dir' / 'a.c',
    ]
    assert filter_files_by_patterns(p, include_globs=['**/*.c', '**/*.h'], default_exclude_globs=[]) == [
        p / 'bar.c',
        p / 'dir' / 'a.c',
        p / 'foo.h',
    ]
    assert filter_files_by_patterns(p, include_globs=['**/*.c', '**/foo*'], default_exclude_globs=[]) == [
        p / 'bar.c',
        p / 'dir' / 'a.c',
        p / 'foo.cc',
        p / 'foo.h',
    ]
    assert filter_files_by_patterns(p, include_globs=[], default_exclude_globs=['**/Makefile']) == [
        p / 'bar.c',
        p / 'dir' / 'a.c',
        p / 'foo.cc',
        p / 'foo.h',
    ]
    assert filter_files_by_patterns(p, include_globs=[], default_exclude_globs=['**/Makefile', '**/foo*']) == [
        p / 'bar.c',
        p / 'dir' / 'a.c',
    ]


def test_filter_files_include_over_default_exclude(tmp_path: Path):
    (tmp_path / 'foo.c').touch()

    assert filter_files_by_patterns(tmp_path, include_globs=['**/*.c'], default_exclude_globs=['**/*.c']) == [
        tmp_path / 'foo.c',
    ]


def test_diff_files(tmp_path: Path):
    name = Path('foo.txt')
    orig_path = tmp_path / name
    orig_path.write_text('hello\nworld\n')

    changed_path = tmp_path / 'changed' / name
    changed_path.parent.mkdir()
    changed_path.write_text('just\nhello\n')

    with chdir(tmp_path):
        assert (
            diff_test_cases(name, changed_path)
            == b"""--- foo.txt
+++ foo.txt
@@ -1,2 +1,2 @@
+just
 hello
-world
"""
        )


def test_diff_dir(tmp_path: Path):
    name = Path('repro')
    orig_path = tmp_path / name
    orig_path.mkdir()
    (orig_path / 'foo.txt').write_text('foo')
    (orig_path / 'bar.txt').write_text('bar')
    (orig_path / 'dir').mkdir()

    changed_path = tmp_path / 'changed' / name
    changed_path.mkdir(parents=True)
    (changed_path / 'bar.txt').write_text('bar')
    (changed_path / 'x.txt').write_text('foo')
    (changed_path / 'other_dir').mkdir()

    with chdir(tmp_path):
        assert (
            diff_test_cases(name, changed_path)
            == b"""--- repro/dir
--- repro/foo.txt
+++ repro/foo.txt
@@ -1 +0,0 @@
-foo
+++ repro/other_dir
--- repro/x.txt
+++ repro/x.txt
@@ -0,0 +1 @@
+foo
"""
        )


def test_remove_extraneous(tmp_path: Path):
    (tmp_path / 'foo.txt').touch()
    (tmp_path / 'bar.txt').touch()
    (tmp_path / 'a').mkdir()
    (tmp_path / 'a' / 'x.txt').touch()
    (tmp_path / 'b').mkdir()
    (tmp_path / 'b' / 'c').mkdir()

    expected_paths = {tmp_path / 'foo.txt', tmp_path / 'a'}
    remove_extraneous_files(tmp_path, expected_paths)

    assert set(tmp_path.rglob('*')) == expected_paths

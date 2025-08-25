import contextlib
import enum
import os
from pathlib import Path
import pytest
import signal
import subprocess
import sys
import tempfile
import time
from typing import Union

from cvise.utils.fileutil import (
    chdir,
    copy_test_case,
    get_file_size,
    get_line_count,
    mkdir_up_to,
    replace_test_case_atomically,
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


class AtomicityResult(enum.Enum):
    CONTENTS_INITIAL = 0
    CONTENTS_NEW = 1
    CONTENTS_UNEXPECTED = 2


def test_replace_atomicity(tmp_path: Path, input_in_source_dir: Path):
    """Verifies whether the file replacement operation is atomic.

    We do this by killing at "random" time points a child process that performs the file replacement.
    """
    INITIAL_DATA = 'a' * 1_000_000
    NEW_DATA = 'b' * 2_000_000
    BINSEARCH_STEPS = 10
    RECHECK_ITERATIONS = 10
    TEST_STEPS = 100

    # Not storing the source file in the tmp_path because to catch non-atomicity the source and the destination have to
    # be on different file systems.
    test_case = Path('a.txt')
    new_dir = tmp_path / 'newdir'
    new_dir.mkdir()

    def do_test(sleep: Union[float, None]) -> AtomicityResult:
        (input_in_source_dir / test_case).write_text(INITIAL_DATA)
        (new_dir / test_case).write_text(NEW_DATA)
        with contextlib.redirect_stderr(None):
            code = (
                'from cvise.utils.fileutil import replace_test_case_atomically; '
                + 'from os import chdir; '
                + 'from pathlib import Path; '
                + f'chdir("{input_in_source_dir}");'
                + f'replace_test_case_atomically(Path("{new_dir / test_case}"), Path("{test_case}"));'
            )
            proc = subprocess.Popen([sys.executable, '-c', code], stderr=subprocess.DEVNULL)
            if sleep is None:
                proc.communicate()
            else:
                time.sleep(sleep)
                os.kill(proc.pid, signal.SIGINT)
            contents = (input_in_source_dir / test_case).read_text()
            if sleep is not None:
                proc.communicate()
        assert len(list(new_dir.iterdir())) <= 1  # the file should remain or got moved
        assert len(list(input_in_source_dir.iterdir())) == 1  # no extra files should appear
        if contents == INITIAL_DATA:
            return AtomicityResult.CONTENTS_INITIAL
        elif contents == NEW_DATA:
            return AtomicityResult.CONTENTS_NEW
        else:
            return AtomicityResult.CONTENTS_UNEXPECTED

    def measure_duration():
        begin_time = time.monotonic()
        assert do_test(sleep=None) == AtomicityResult.CONTENTS_NEW
        return time.monotonic() - begin_time

    # Estimate using binary search the "critical" time - how long it takes for the code-under-test to start modifying
    # the input file.
    left = 0
    right = measure_duration()
    for _ in range(BINSEARCH_STEPS):
        mid = (left + right) / 2
        all_initial = all(do_test(mid) == AtomicityResult.CONTENTS_INITIAL for _ in range(RECHECK_ITERATIONS))
        if all_initial:
            left = mid
        else:
            right = mid
    critical_time = left

    # Test the atomicity by trying to kill the process at various times around the critical time, and checking whether
    # the file exists and has one of expected values ("before" or "after").
    for i in range(TEST_STEPS):
        deviation = critical_time / TEST_STEPS * i
        assert do_test(critical_time + deviation) != AtomicityResult.CONTENTS_UNEXPECTED
        assert do_test(critical_time - deviation) != AtomicityResult.CONTENTS_UNEXPECTED

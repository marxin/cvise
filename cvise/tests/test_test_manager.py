import glob
import os
import pytest
import shutil
from unittest.mock import patch

from cvise.passes.abstract import AbstractPass, PassResult  # noqa: E402
from cvise.utils import statistics, testing  # noqa: E402


INPUT_DATA = """foo
bar
baz
"""


class StubPass(AbstractPass):
    def __init__(self):
        super().__init__()
        self.max_transforms = None

    def new(self, test_case, check_sanity):
        return 0

    def advance(self, test_case, state):
        return state + 1

    def advance_on_success(self, test_case, state):
        return state


class NaiveLinePass(StubPass):
    """Simple real-world-like pass that removes a line at a time."""

    def transform(self, test_case, state, process_event_notifier):
        with open(test_case) as f:
            lines = f.readlines()
        if not lines:
            return (PassResult.STOP, state)

        cut = state % len(lines)
        remained = lines[:cut] + lines[cut + 1 :]

        with open(test_case, 'w') as f:
            f.writelines(remained)
        return (PassResult.OK, state)


class AlwaysInvalidPass(StubPass):
    """Never succeeds."""

    def transform(self, test_case, state, process_event_notifier):
        return (PassResult.INVALID, state)


class NInvalidThenLinesPass(NaiveLinePass):
    """Starts removing lines after the first N invalid results."""

    def __init__(self, invalid_n):
        super().__init__()
        self.invalid_n = invalid_n

    def transform(self, test_case, state, process_event_notifier):
        if state < self.invalid_n:
            return (PassResult.INVALID, state)
        return super().transform(test_case, state, process_event_notifier)


class OneOffLinesPass(NaiveLinePass):
    """Removes a single line but doesn't progress further."""

    def advance_on_success(self, test_case, state):
        return None


class AlwaysUnalteredPass(StubPass):
    """Simulates the "buggy OKs infinite number of times" scenario."""

    def transform(self, test_case, state, process_event_notifier):
        return (PassResult.OK, state)


def read_file(path):
    with open(path) as f:
        return f.read()


def count_lines(path):
    with open(path) as f:
        return len(f.readlines())


def bug_dir_count():
    pattern = testing.TestManager.BUG_DIR_PREFIX + '*'
    return len(glob.glob(pattern))


# Run all tests in the temp dir, to prevent artifacts like the cvise_bug_* from appearing in the build directory.
@pytest.fixture(autouse=True)
def cwd_to_tmp_path(tmp_path):
    old_cwd = os.getcwd()
    os.chdir(tmp_path)
    yield
    os.chdir(old_cwd)


@pytest.fixture
def input_file(tmp_path):
    RELATIVE_PATH = 'input.txt'
    path = tmp_path / RELATIVE_PATH
    with open(path, 'w') as f:
        f.write(INPUT_DATA)
    return RELATIVE_PATH


@pytest.fixture
def interestingness_script():
    path = shutil.which('true')
    assert path
    return path


@pytest.fixture
def manager(input_file, interestingness_script):
    TIMEOUT = 100
    SAVE_TEMPS = False
    N = 10
    NO_CACHE = False
    SKIP_KEY_OFF = True  # tests shouldn't listen to keyboard
    SHADDAP = False
    DIE_ON_PASS_BUG = False
    PRINT_DIFF = False
    MAX_IMPROVEMENT = None
    NO_GIVE_UP = False
    ALSO_INTERESTING = None
    START_WITH_PASS = None
    SKIP_AFTER_N_TRANSFORMS = None
    STOPPING_THRESHOLD = 1.0
    pass_statistic = statistics.PassStatistic()
    return testing.TestManager(
        pass_statistic,
        interestingness_script,
        TIMEOUT,
        SAVE_TEMPS,
        [input_file],
        N,
        NO_CACHE,
        SKIP_KEY_OFF,
        SHADDAP,
        DIE_ON_PASS_BUG,
        PRINT_DIFF,
        MAX_IMPROVEMENT,
        NO_GIVE_UP,
        ALSO_INTERESTING,
        START_WITH_PASS,
        SKIP_AFTER_N_TRANSFORMS,
        STOPPING_THRESHOLD,
    )


def test_succeed_via_naive_pass(input_file, manager):
    """Check that we completely empty the file via the naive lines pass."""
    p = NaiveLinePass()
    manager.run_pass(p)
    assert read_file(input_file) == ''
    assert bug_dir_count() == 0


def test_succeed_via_n_one_off_passes(input_file, manager):
    """Check that we succeed after running one-off passes multiple times."""
    LINES = len(INPUT_DATA.splitlines())
    for lines in range(LINES, 0, -1):
        assert count_lines(input_file) == lines
        p = OneOffLinesPass()
        manager.run_pass(p)
        assert count_lines(input_file) == lines - 1
    assert bug_dir_count() == 0


def test_succeed_after_n_invalid_results(input_file, manager):
    """Check that we still succeed even if the first few invocations were unsuccessful."""
    INVALID_N = 15
    p = NInvalidThenLinesPass(INVALID_N)
    manager.run_pass(p)
    assert read_file(input_file) == ''
    assert bug_dir_count() == 0


@patch('cvise.utils.testing.TestManager.GIVEUP_CONSTANT', 100)
def test_give_up_on_stuck_pass(input_file, manager):
    """Check that we quit if the pass doesn't improve for a long time."""
    p = AlwaysInvalidPass()
    manager.run_pass(p)
    assert read_file(input_file) == INPUT_DATA
    # The "pass got stuck" report.
    assert bug_dir_count() == 1


def test_halt_on_unaltered(input_file, manager):
    """Check that we quit if the pass keeps misbehaving."""
    p = AlwaysUnalteredPass()
    manager.run_pass(p)
    assert read_file(input_file) == INPUT_DATA
    # This number of "failed to modify the variant" reports were to be created.
    assert bug_dir_count() == testing.TestManager.MAX_CRASH_DIRS + 1

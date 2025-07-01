import glob
import os
from pathlib import Path
import pytest
import time
from unittest.mock import patch

from cvise.passes.abstract import AbstractPass, PassResult  # noqa: E402
from cvise.utils import keyboard_interrupt_monitor, statistics, testing  # noqa: E402


INPUT_DATA = """foo
bar
baz
"""

PARALLEL_TESTS = 10


class StubPass(AbstractPass):
    def __init__(self):
        super().__init__()
        self.max_transforms = None

    def new(self, test_case, **kwargs):
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


class SlowUnalteredThenStoppingPass(StubPass):
    """Attempts to simulate the "STOP event observed before a buggy OK" scenario."""

    DELAY_SECS = 1  # the larger the number, the higher the chance of catching bugs

    def transform(self, test_case, state, process_event_notifier):
        if state == 0:
            time.sleep(self.DELAY_SECS)
            return (PassResult.OK, state)
        return (PassResult.STOP, state)


class LetterRemovingPass(StubPass):
    """Attempts removing letters from the specified vocabulary.

    In this pass, the state is interpreted as the index among all matching letters."""

    def __init__(self, letters_to_remove):
        super().__init__()
        self.letters_to_remove = letters_to_remove

    def transform(self, test_case, state, process_event_notifier):
        text = read_file(test_case)
        instances = 0
        for i, c in enumerate(text):
            if c in self.letters_to_remove:
                if instances == state:
                    # Found a matching letter with the expected index; remove it.
                    Path(test_case).write_text(text[:i] + text[i + 1 :])
                    return (PassResult.OK, state)
                instances += 1
        return (PassResult.STOP, state)


def read_file(path):
    with open(path) as f:
        return f.read()


def count_lines(path):
    with open(path) as f:
        return len(f.readlines())


def bug_dir_count():
    pattern = testing.TestManager.BUG_DIR_PREFIX + '*'
    return len(glob.glob(pattern))


@pytest.fixture(autouse=True)
def interrupt_monitor():
    keyboard_interrupt_monitor.init()


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
    return Path(RELATIVE_PATH)


@pytest.fixture
def interestingness_script():
    """The default interestingness script, which trivially returns success.

    Can be overridden in particular tests."""
    # Just eat the test file name.
    return 'true {test_case}'


@pytest.fixture
def manager(tmp_path, input_file, interestingness_script):
    TIMEOUT = 100
    SAVE_TEMPS = False
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

    script_path = tmp_path / 'check.sh'
    script_path.write_text(interestingness_script.format(test_case=input_file))
    script_path.chmod(0o744)

    return testing.TestManager(
        pass_statistic,
        script_path,
        TIMEOUT,
        SAVE_TEMPS,
        [input_file],
        PARALLEL_TESTS,
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
    manager.run_passes([p])
    assert read_file(input_file) == ''
    assert bug_dir_count() == 0


def test_succeed_via_n_one_off_passes(input_file, manager):
    """Check that we succeed after running one-off passes multiple times."""
    LINES = len(INPUT_DATA.splitlines())
    for lines in range(LINES, 0, -1):
        assert count_lines(input_file) == lines
        p = OneOffLinesPass()
        manager.run_passes([p])
        assert count_lines(input_file) == lines - 1
    assert bug_dir_count() == 0


def test_succeed_after_n_invalid_results(input_file, manager):
    """Check that we still succeed even if the first few invocations were unsuccessful."""
    INVALID_N = 15
    p = NInvalidThenLinesPass(INVALID_N)
    manager.run_passes([p])
    assert read_file(input_file) == ''
    assert bug_dir_count() == 0


@patch('cvise.utils.testing.TestManager.GIVEUP_CONSTANT', 100)
def test_give_up_on_stuck_pass(input_file, manager):
    """Check that we quit if the pass doesn't improve for a long time."""
    p = AlwaysInvalidPass()
    manager.run_passes([p])
    assert read_file(input_file) == INPUT_DATA
    # The "pass got stuck" report.
    assert bug_dir_count() == 1


def test_halt_on_unaltered(input_file, manager):
    """Check that we quit if the pass keeps misbehaving."""
    p = AlwaysUnalteredPass()
    manager.run_passes([p])
    assert read_file(input_file) == INPUT_DATA
    # This number of "failed to modify the variant" reports were to be created.
    assert bug_dir_count() == testing.TestManager.MAX_CRASH_DIRS + 1


def test_halt_on_unaltered_after_stop(input_file, manager):
    """Check that we quit after the pass' stop, even if it interleaved with a misbehave."""
    p = SlowUnalteredThenStoppingPass()
    manager.run_passes([p])
    assert read_file(input_file) == INPUT_DATA
    # Whether the misbehave ("failed to modify the variant") is detected depends on timing.
    assert bug_dir_count() <= 1


def test_interleaving_letter_removals(input_file, manager):
    """Test that two different passes executed in interleaving way remove different letters."""
    p1 = LetterRemovingPass('fz')
    p2 = LetterRemovingPass('b')
    while True:
        value_before = read_file(input_file)
        manager.run_passes([p1, p2])
        if read_file(input_file) == value_before:
            break

    assert read_file(input_file) == 'oo\nar\na\n'


@pytest.mark.skipif(os.name != 'posix', reason='requires POSIX for command-line tools')
@pytest.mark.parametrize('interestingness_script', [r"grep a {test_case} && ! grep '\(.\)\1' {test_case}"])
def test_interleaving_letter_removals_large(input_file, manager):
    """Test that multiple passes executed in interleaving way can delete all but one characters.

    The interestingness test here is "there's the `a` character and no character is repeated twice in a row", which for
    the given test requires alternating between removing `a`, `b` and `c` many times."""
    input_file.write_text('ababacac' * PARALLEL_TESTS)
    p1 = LetterRemovingPass('a')
    p2 = LetterRemovingPass('b')
    p3 = LetterRemovingPass('c')
    while True:
        value_before = read_file(input_file)
        manager.run_passes([p1, p2, p3])
        if read_file(input_file) == value_before:
            break

    assert read_file(input_file) == 'a'

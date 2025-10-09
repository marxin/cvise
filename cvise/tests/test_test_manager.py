import contextlib
import glob
import logging
import multiprocessing
import os
from pathlib import Path
import psutil
import pytest
import re
import sys
import time
from typing import Dict, List, Union
from unittest.mock import patch

from cvise.passes.abstract import AbstractPass, PassResult  # noqa: E402
from cvise.passes.hint_based import HintBasedPass  # noqa: E402
from cvise.utils import sigmonitor, statistics, testing  # noqa: E402
from cvise.utils.fileutil import filter_files_by_patterns
from cvise.utils.hint import Hint, HintBundle, Patch


DEFAULT_INPUT_CONTENTS = """foo
bar
baz
"""

PARALLEL_TESTS = 10


class StubPass(AbstractPass):
    def new(self, test_case: Path, *args, **kwargs):
        return 0

    def advance(self, test_case: Path, state):
        return state + 1

    def advance_on_success(self, test_case: Path, state, *args, **kwargs):
        return state


class NaiveLinePass(StubPass):
    """Simple real-world-like pass that removes a line at a time."""

    def transform(self, test_case: Path, state, *args, **kwargs):
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

    def transform(self, test_case: Path, state, *args, **kwargs):
        return (PassResult.INVALID, state)


class HungPass(StubPass):
    """A very slow pass, for testing timeouts."""

    def transform(self, test_case: Path, state, *args, **kwargs):
        INFINITY = 1000
        time.sleep(INFINITY)
        return (PassResult.INVALID, state)


class InvalidAndEveryNLinesPass(NaiveLinePass):
    """Removes a line every N job; others exit with INVALID."""

    def __init__(self, invalid_n):
        super().__init__()
        self.invalid_n = invalid_n

    def transform(self, test_case: Path, state, *args, **kwargs):
        if (state + 1) % self.invalid_n != 0:
            return (PassResult.INVALID, state)
        return super().transform(test_case, state // self.invalid_n, *args, **kwargs)


class OneOffLinesPass(NaiveLinePass):
    """Removes a single line but doesn't progress further."""

    def advance_on_success(self, test_case: Path, state, **kwargs):
        return None


class AlwaysUnalteredPass(StubPass):
    """Simulates the "buggy OKs infinite number of times" scenario."""

    def transform(self, test_case: Path, state, *args, **kwargs):
        return (PassResult.OK, state)


class SlowUnalteredThenStoppingPass(StubPass):
    """Attempts to simulate the "STOP event observed before a buggy OK" scenario."""

    DELAY_SECS = 1  # the larger the number, the higher the chance of catching bugs

    def transform(self, test_case: Path, state, *args, **kwargs):
        if state == 0:
            time.sleep(self.DELAY_SECS)
            return (PassResult.OK, state)
        return (PassResult.STOP, state)


class LetterRemovingPass(StubPass):
    """Attempts removing letters from the specified vocabulary.

    In this pass, the state is interpreted as the index among all matching letters."""

    def __init__(self, letters_to_remove: str):
        super().__init__()
        self._letters_to_remove = letters_to_remove

    def transform(self, test_case: Path, state, *args, **kwargs):
        text = test_case.read_text()
        instances = 0
        for i, c in enumerate(text):
            if c in self._letters_to_remove:
                if instances == state:
                    # Found a matching letter with the expected index; remove it.
                    test_case.write_text(text[:i] + text[i + 1 :])
                    return (PassResult.OK, state)
                instances += 1
        return (PassResult.STOP, state)


class LetterRemovingHintPass(HintBasedPass):
    def __init__(self, letters_to_remove: str, **kwargs):
        super().__init__(arg=letters_to_remove, **kwargs)
        self._letters_to_remove = letters_to_remove

    def supports_dir_test_cases(self):
        return True

    def generate_hints(self, test_case: Path, *args, **kwargs):
        hints = []
        paths = filter_files_by_patterns(test_case, self.claim_files, self.claimed_by_others_files)
        vocab = [str(p.relative_to(test_case)).encode() for p in paths]
        for file_id, path in enumerate(paths):
            data = path.read_text()
            for i, c in enumerate(data):
                if c in self._letters_to_remove:
                    hints.append(Hint(patches=(Patch(left=i, right=i + 1, file=file_id),)))
        return HintBundle(hints=hints, vocabulary=vocab)


class TracingHintPass(LetterRemovingHintPass):
    def __init__(self, queue, letters_to_remove: str):
        super().__init__(letters_to_remove)
        self._queue = queue

    def transform(self, test_case: Path, state, *args, **kwargs):
        self._queue.put(self.arg)
        return super().transform(test_case, state, *args, **kwargs)


class BracketRemovingPass(HintBasedPass):
    """Attempts removing pairs of brackets (not nested) and their contents."""

    def output_hint_types(self):
        return [b'remove-brackets']

    def generate_hints(self, test_case: Path, *args, **kwargs):
        hints = []
        for m in re.finditer(r'\([^()]*\)', test_case.read_text()):
            hints.append(Hint(type=0, patches=(Patch(left=m.start(), right=m.end()),)))
        return HintBundle(hints=hints, vocabulary=[b'remove-brackets'])


class InsideBracketsRemovingPass(HintBasedPass):
    """Attempts removing contents inside brackets.

    Uses the hints produced by BracketRemovingPass instead of searching for the brackets itself - this is useful for
    testing dependencies between passes.
    """

    def input_hint_types(self):
        return [b'remove-brackets']

    def generate_hints(self, test_case: Path, dependee_hints: List[HintBundle], *args, **kwargs):
        hints = []
        for input_bundle in dependee_hints:
            for input_hint in input_bundle.hints:
                assert input_bundle.vocabulary[input_hint.type] == b'remove-brackets'
                assert len(input_hint.patches) == 1
                input_patch = input_hint.patches[0]
                if input_patch.right - input_patch.left == 1:
                    continue  # don't create empty hints
                hints.append(Hint(patches=(Patch(left=input_patch.left + 1, right=input_patch.right - 1),)))
        return HintBundle(hints=hints)


def count_lines(path: Path) -> int:
    with open(path) as f:
        return len(f.readlines())


def bug_dir_count():
    pattern = testing.TestManager.BUG_DIR_PREFIX + '*'
    return len(glob.glob(pattern))


def extra_dir_count():
    pattern = testing.TestManager.EXTRA_DIR_PREFIX + '*'
    return len(glob.glob(pattern))


@pytest.fixture(autouse=True)
def signal_monitor():
    sigmonitor.init(sigmonitor.Mode.RAISE_EXCEPTION)


# Run all tests in the temp dir, to prevent artifacts like the cvise_bug_* from appearing in the build directory.
@pytest.fixture(autouse=True)
def cwd_to_tmp_path(tmp_path: Path):
    old_cwd = os.getcwd()
    os.chdir(tmp_path)
    yield
    os.chdir(old_cwd)


@pytest.fixture
def input_contents() -> Union[str, Dict[Path, str]]:
    return DEFAULT_INPUT_CONTENTS


@pytest.fixture
def input_path(tmp_path: Path, input_contents: Union[str, Dict[Path, str]]) -> Path:
    RELATIVE_PATH = Path('test_case')
    path = tmp_path / RELATIVE_PATH
    if isinstance(input_contents, str):
        path.write_text(input_contents)
    else:
        for rel_path, contents in input_contents.items():
            (path / rel_path).parent.mkdir(parents=True, exist_ok=True)
            (path / rel_path).write_text(contents)
    return Path(RELATIVE_PATH)


@pytest.fixture
def interestingness_script() -> str:
    """The default interestingness script, which trivially returns success.

    Can be overridden in particular tests."""
    # Just eat the test file name.
    return 'true {test_case}'


@pytest.fixture
def job_timeout() -> int:
    """The default job timeout.

    Can be overridden in particular tests.
    """
    return 100


@pytest.fixture
def print_diff() -> bool:
    """The default print_diff parameter.

    Can be overridden in particular tests.
    """
    return False


@pytest.fixture
def with_tty(mocker) -> None:
    mocker.patch.object(sys.stdout, 'isatty', lambda: True)


@pytest.fixture
def without_colordiff(fp, with_tty) -> None:
    fp.register(['colordiff', '--version'], returncode=1)


@pytest.fixture
def with_colordiff(fp, with_tty) -> None:
    fp.register(['colordiff', '--version'])


@pytest.fixture
def manager(tmp_path: Path, input_path: Path, interestingness_script: str, job_timeout: int, print_diff: bool):
    SAVE_TEMPS = False
    NO_CACHE = False
    SKIP_KEY_OFF = True  # tests shouldn't listen to keyboard
    SHADDAP = False
    DIE_ON_PASS_BUG = False
    MAX_IMPROVEMENT = None
    NO_GIVE_UP = False
    ALSO_INTERESTING = None
    START_WITH_PASS = None
    SKIP_AFTER_N_TRANSFORMS = None
    STOPPING_THRESHOLD = 1.0
    pass_statistic = statistics.PassStatistic()

    script_path = tmp_path / 'check.sh'
    script_path.write_text(interestingness_script.format(test_case=input_path))
    script_path.chmod(0o744)

    test_manager = testing.TestManager(
        pass_statistic,
        script_path,
        job_timeout,
        SAVE_TEMPS,
        [input_path],
        PARALLEL_TESTS,
        NO_CACHE,
        SKIP_KEY_OFF,
        SHADDAP,
        DIE_ON_PASS_BUG,
        print_diff,
        MAX_IMPROVEMENT,
        NO_GIVE_UP,
        ALSO_INTERESTING,
        START_WITH_PASS,
        SKIP_AFTER_N_TRANSFORMS,
        STOPPING_THRESHOLD,
    )
    test_manager.__enter__()
    try:
        yield test_manager
    finally:
        if test_manager.worker_pool:  # some tests shut down the manager themselves
            test_manager.__exit__(None, None, None)


def test_succeed_via_naive_pass(input_path: Path, manager):
    """Check that we completely empty the file via the naive lines pass."""
    p = NaiveLinePass()
    manager.run_passes([p], interleaving=False)
    assert input_path.read_text() == ''
    assert bug_dir_count() == 0


def test_succeed_via_n_one_off_passes(input_path: Path, manager):
    """Check that we succeed after running one-off passes multiple times."""
    LINES = len(DEFAULT_INPUT_CONTENTS.splitlines())
    for lines in range(LINES, 0, -1):
        assert count_lines(input_path) == lines
        p = OneOffLinesPass()
        manager.run_passes([p], interleaving=False)
        assert count_lines(input_path) == lines - 1
    assert bug_dir_count() == 0


def test_succeed_after_n_invalid_results(input_path: Path, manager):
    """Check that we still succeed even if the first few invocations were unsuccessful."""
    INVALID_N = 15
    p = InvalidAndEveryNLinesPass(INVALID_N)
    manager.run_passes([p], interleaving=False)
    assert input_path.read_text() == ''
    assert bug_dir_count() == 0


@patch('cvise.utils.testing.TestManager.GIVEUP_CONSTANT', 100)
def test_give_up_on_stuck_pass(input_path: Path, manager):
    """Check that we quit if the pass doesn't improve for a long time."""
    p = AlwaysInvalidPass()
    manager.run_passes([p], interleaving=False)
    assert input_path.read_text() == DEFAULT_INPUT_CONTENTS
    # The "pass got stuck" report.
    assert bug_dir_count() == 1


@patch('cvise.utils.testing.TestManager.GIVEUP_CONSTANT', 100)
def test_interleaving_gives_up_only_stuck_passes(input_path: Path, manager):
    """Check that when some passes get stuck in interleaving mode, others continue to be used."""
    stuck_pass = AlwaysInvalidPass()
    occasionally_working_pass = InvalidAndEveryNLinesPass(testing.TestManager.GIVEUP_CONSTANT // 3)
    manager.run_passes([stuck_pass, occasionally_working_pass], interleaving=True)
    assert input_path.read_text() == ''
    # The "pass got stuck" report (for the stuck pass).
    assert bug_dir_count() == 1


def test_halt_on_unaltered(input_path: Path, manager):
    """Check that we quit if the pass keeps misbehaving."""
    p = AlwaysUnalteredPass()
    manager.run_passes([p], interleaving=False)
    assert input_path.read_text() == DEFAULT_INPUT_CONTENTS
    # This number of "failed to modify the variant" reports were to be created.
    assert bug_dir_count() == testing.TestManager.MAX_CRASH_DIRS + 1


def test_halt_on_unaltered_after_stop(input_path: Path, manager):
    """Check that we quit after the pass' stop, even if it interleaved with a misbehave."""
    p = SlowUnalteredThenStoppingPass()
    manager.run_passes([p], interleaving=False)
    assert input_path.read_text() == DEFAULT_INPUT_CONTENTS
    # Whether the misbehave ("failed to modify the variant") is detected depends on timing.
    assert bug_dir_count() <= 1


@pytest.mark.parametrize('job_timeout', [1])
def test_give_up_on_repeating_timeouts(input_path: Path, manager):
    p = HungPass()
    manager.run_passes([p], interleaving=False)
    assert extra_dir_count() >= manager.MAX_TIMEOUTS
    # we should've stopped soon after MAX_TIMEOUTS, at worst a batch of jobs later.
    assert extra_dir_count() <= 2 * max(manager.MAX_TIMEOUTS, PARALLEL_TESTS)


def test_interleaving_letter_removals(input_path: Path, manager):
    """Test that two different passes executed in interleaving way remove different letters."""
    p1 = LetterRemovingPass('fz')
    p2 = LetterRemovingPass('b')
    while True:
        value_before = input_path.read_text()
        manager.run_passes([p1, p2], interleaving=True)
        if input_path.read_text() == value_before:
            break

    assert input_path.read_text() == 'oo\nar\na\n'


@pytest.mark.skipif(os.name != 'posix', reason='requires POSIX for command-line tools')
@pytest.mark.parametrize('input_contents', ['ababacac' * PARALLEL_TESTS])
@pytest.mark.parametrize('interestingness_script', [r"grep a {test_case} && ! grep '\(.\)\1' {test_case}"])
def test_interleaving_letter_removals_large(input_path: Path, manager):
    """Test that multiple passes executed in interleaving way can delete all but one character.

    The interestingness test here is "there's the `a` character and no character is repeated twice in a row", which for
    the given test requires alternating between removing `a`, `b` and `c` many times."""
    p1 = LetterRemovingPass('a')
    p2 = LetterRemovingPass('b')
    p3 = LetterRemovingPass('c')
    while True:
        value_before = input_path.read_text()
        manager.run_passes([p1, p2, p3], interleaving=True)
        if input_path.read_text() == value_before:
            break

    assert input_path.read_text() == 'a'


@pytest.mark.skipif(os.name != 'posix', reason='requires POSIX for command-line tools')
@pytest.mark.parametrize('interestingness_script', [r'false {test_case}'])
def test_interleaving_round_robin_transforms(manager: testing.TestManager):
    tracing_queue = multiprocessing.Manager().Queue()
    passes = [TracingHintPass(tracing_queue, letters_to_remove=chr(ord('a') + i)) for i in range(PARALLEL_TESTS)]
    manager.run_passes(passes, interleaving=True)

    transform_calls = []
    while not tracing_queue.empty():
        transform_calls.append(tracing_queue.get())

    # all passes should've gotten equal number of jobs
    execs_per_pass = [transform_calls.count(str(i)) for i in range(PARALLEL_TESTS)]
    assert min(execs_per_pass) == max(execs_per_pass)
    # we cannot assert the ideal round-robin order (like 123..N123..) because concurrent writes to the queue are racy,
    # but at least it's almost guaranteed that no pass should be recorded N times in a row.
    for i in range(len(transform_calls) - PARALLEL_TESTS + 1):
        slice = transform_calls[i : i + PARALLEL_TESTS]
        assert min(slice) != max(slice)


@pytest.mark.skipif(os.name != 'posix', reason='requires POSIX for command-line tools')
@pytest.mark.parametrize('input_contents', [{Path('foo.txt'): 'abacaba', Path('bar.txt'): 'ddaabbcc'}])
def test_interleaving_letter_removals_directory(input_path: Path, manager):
    """Test the letter removal passes for a directory input."""
    p1 = LetterRemovingHintPass('a')
    p2 = LetterRemovingHintPass('b')
    p3 = LetterRemovingHintPass('c')
    while True:
        files_before = _read_files_in_dir(input_path)
        manager.run_passes([p1, p2, p3], interleaving=True)
        if _read_files_in_dir(input_path) == files_before:
            break

    assert _read_files_in_dir(input_path) == {Path('foo.txt'): '', Path('bar.txt'): 'dd'}


@pytest.mark.skipif(os.name != 'posix', reason='requires POSIX for command-line tools')
@pytest.mark.parametrize('input_contents', [{Path('foo.txt'): 'abacaba', Path('bar.txt'): 'ddaabbcc'}])
def test_interleaving_letter_removals_directory_claimed_files(input_path: Path, manager):
    """Test that passes only modify files they claim."""
    p1 = LetterRemovingHintPass('ab', claim_files=['foo*'])
    p2 = LetterRemovingHintPass('bc', claim_files=['bar*'])
    while True:
        files_before = _read_files_in_dir(input_path)
        manager.run_passes([p1, p2], interleaving=True)
        if _read_files_in_dir(input_path) == files_before:
            break

    assert _read_files_in_dir(input_path) == {Path('foo.txt'): 'c', Path('bar.txt'): 'ddaa'}


@pytest.mark.parametrize('print_diff', [True])
def test_print_diff(
    without_colordiff: None,
    manager: testing.TestManager,
    caplog: pytest.LogCaptureFixture,
    fp,
):
    fp.allow_unregistered(allow=True)  # allow C-Vise workers
    pass_ = NaiveLinePass()
    with caplog.at_level(logging.INFO):
        manager.run_passes([pass_], interleaving=True)
        # ensure logs are flushed by shutting down the manager
        manager.__exit__(None, None, None)

    assert '-foo\n' in caplog.text
    assert '-bar\n' in caplog.text
    assert '-baz\n' in caplog.text


@pytest.mark.parametrize('print_diff', [True])
def test_print_diff_colordiff(
    with_colordiff: None,
    manager: testing.TestManager,
    caplog: pytest.LogCaptureFixture,
    fp,
):
    def colordiff_callback(stdin: bytes) -> Dict[str, bytes]:
        lines = [b'\x1b[1;37m' + s + b'\x1b[0;0m' for s in stdin.splitlines()]
        return {'stdout': b'\n'.join(lines)}

    fp.register(['colordiff'], stdin_callable=colordiff_callback)
    fp.keep_last_process(keep=True)  # colordiff is called multiple times
    fp.allow_unregistered(allow=True)  # allow C-Vise workers
    pass_ = NaiveLinePass()
    with caplog.at_level(logging.INFO):
        manager.run_passes([pass_], interleaving=True)
        # ensure logs are flushed by shutting down the manager
        manager.__exit__(None, None, None)

    log = '\n'.join(r.message for r in caplog.records)  # caplog.text would strip ANSI escape codes
    assert '\x1b[1;37m-foo\x1b[0;0m\n' in log
    assert '\x1b[1;37m-bar\x1b[0;0m\n' in log
    assert '\x1b[1;37m-baz\x1b[0;0m\n' in log


@pytest.mark.parametrize('print_diff', [True])
def test_print_diff_colordiff_failure(
    with_colordiff: None,
    manager: testing.TestManager,
    caplog: pytest.LogCaptureFixture,
    fp,
):
    fp.register(['colordiff'], returncode=1)
    fp.keep_last_process(keep=True)  # colordiff is called multiple times
    fp.allow_unregistered(allow=True)  # allow C-Vise workers
    pass_ = NaiveLinePass()
    with caplog.at_level(logging.INFO):
        manager.run_passes([pass_], interleaving=True)
        # ensure logs are flushed by shutting down the manager
        manager.__exit__(None, None, None)

    assert '-foo\n' in caplog.text
    assert '-bar\n' in caplog.text
    assert '-baz\n' in caplog.text


def _unique_sleep_infinity() -> str:
    """Generates a big parameter for the "sleep" command-line tool, such that it's unique for our test invocation.

    Useful for identifying processes that were spawned by the code-under-test.
    """
    return f'100.12345{os.getpid()}'


# "ids" is used to ensure the test id is the same regardless of the test runner process (relevant for pytest-xdist)
@pytest.mark.skipif(os.name != 'posix', reason='requires POSIX for command-line tools')
@pytest.mark.parametrize('job_timeout', [1])
@pytest.mark.parametrize('interestingness_script', [f'sleep {_unique_sleep_infinity()}'], ids=[''])
def test_subprocess_termination(manager: testing.TestManager):
    """Verifies that spawned "hung" subprocesses are terminated."""
    p = NaiveLinePass()
    manager.run_passes([p], interleaving=False)
    # ensure process termination logic completes by shutting down the manager
    manager.__exit__(None, None, None)
    assert _find_processes_by_cmd_line(_unique_sleep_infinity()) == []


def _find_processes_by_cmd_line(needle: str) -> List[psutil.Process]:
    processes = []
    for proc in psutil.process_iter():
        with contextlib.suppress(psutil.NoSuchProcess, psutil.ZombieProcess):
            if needle in proc.cmdline():
                processes.append(proc)
    return processes


@pytest.mark.skipif(os.name != 'posix', reason='requires POSIX for command-line tools')
@pytest.mark.parametrize('input_contents', ['a(b)c(de)'])
@pytest.mark.parametrize('interestingness_script', [r"grep '[(][)].*[(][)]' {test_case}"])
def test_pass_dependency(input_path: Path, manager: testing.TestManager):
    """Test a pass that depends on another pass' hints works correctly.

    Here, the first pass produces hints that point to pairs of brackets; these hints themselves don't pass the
    interestingness test. The second pass uses the first pass' hints to produce new ones that remove contents inside
    brackets - this is what we expect to succeed.
    """
    passes = [BracketRemovingPass(), InsideBracketsRemovingPass()]
    manager.run_passes(passes, interleaving=True)
    assert input_path.read_text() == 'a()c()'


def _read_files_in_dir(dir: Path) -> Dict[Path, str]:
    return {p.relative_to(dir): p.read_text() for p in dir.rglob('*') if not p.is_dir()}

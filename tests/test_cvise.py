import os
from pathlib import Path
import pytest
import shutil
import signal
import stat
import subprocess
import time


SUBPROCESS_TMPDIR = 'tmpdir'


def start_cvise(arguments, tmp_path: Path):
    current = os.path.dirname(__file__)
    binary = os.path.join(current, '../cvise-cli.py')
    cmd = [binary] + arguments

    new_tmpdir = tmp_path / SUBPROCESS_TMPDIR
    new_tmpdir.mkdir()
    new_env = os.environ.copy()
    new_env['TMPDIR'] = str(new_tmpdir)

    return subprocess.Popen(cmd, stdout=subprocess.PIPE, encoding='utf8', env=new_env)


def check_cvise(testcase, arguments, expected, tmp_path: Path):
    current = os.path.dirname(__file__)
    shutil.copy(os.path.join(current, 'sources', testcase), '.')
    os.chmod(testcase, 0o644)
    proc = start_cvise([testcase] + arguments, tmp_path)
    proc.communicate()
    assert proc.returncode == 0

    with open(testcase) as f:
        content = f.read()
    assert content in expected
    assert stat.filemode(os.stat(testcase).st_mode) == '-rw-r--r--'
    assert_subprocess_tmpdir_empty(tmp_path)


def wait_until_file_created(path: Path):
    while not path.exists():
        time.sleep(0.1)


def assert_subprocess_tmpdir_empty(tmp_path: Path) -> None:
    assert list((tmp_path / SUBPROCESS_TMPDIR).iterdir()) == []


def test_simple_reduction(tmp_path: Path):
    check_cvise(
        'blocksort-part.c',
        ['-c', r"gcc -c blocksort-part.c && grep '\<nextHi\>' blocksort-part.c"],
        ['#define nextHi'],
        tmp_path,
    )


def test_simple_reduction_no_interleaving_config(tmp_path: Path):
    check_cvise(
        'blocksort-part.c',
        ['-c', r"gcc -c blocksort-part.c && grep '\<nextHi\>' blocksort-part.c", '--pass-group', 'no-interleaving'],
        ['#define nextHi'],
        tmp_path,
    )


@pytest.mark.skipif(os.name != 'posix', reason='requires POSIX for command-line tools')
@pytest.mark.parametrize('additional_delay', [0, 1, 10])
def test_ctrl_c(tmp_path: Path, additional_delay: int):
    """Test that Control-C is handled quickly, without waiting for jobs to finish."""
    MAX_SHUTDOWN = 10  # in seconds; tolerance to prevent flakiness (normally it's a fraction of a second)
    JOB_SLOWNESS = MAX_SHUTDOWN * 2  # make a single job slower than the thresholds

    flag_file = tmp_path / 'flag'

    proc = start_cvise(
        [
            'blocksort-part.c',
            '-c',
            f'gcc -c blocksort-part.c && touch {flag_file} && sleep {JOB_SLOWNESS}',
            '--skip-interestingness-test-check',
        ],
        tmp_path,
    )
    # to make the test cover the interesting scenario, we wait until C-Vise starts at least one job
    wait_until_file_created(flag_file)
    # extra wait for more variance in test scenarios
    time.sleep(additional_delay)

    proc.send_signal(signal.SIGINT)
    try:
        proc.communicate(timeout=MAX_SHUTDOWN)
    except TimeoutError:
        # C-Vise has not quit on time - kill it and fail the test
        proc.kill()
        raise
    assert_subprocess_tmpdir_empty(tmp_path)


def test_interleaving_lines_passes(tmp_path: Path):
    """Test a pass group config with an interleaving category."""
    config_path = tmp_path / 'config.json'
    config_path.write_text("""
        {"interleaving": [
            {"pass": "lines", "arg": "0"},
            {"pass": "lines", "arg": "1"},
            {"pass": "lines", "arg": "2"}
         ]
        }""")

    testcase_path = tmp_path / 'test.c'
    testcase_path.write_text("""
        int bar() {
          return 42;
        }
        int foo() {
          return bar();
        }
        int main() {
          return foo();
        }
        """)
    shutil.copy(testcase_path, '.')
    copy_path = Path(testcase_path.name)

    proc = start_cvise(
        ['-c', 'gcc -c test.c && grep foo test.c', '--pass-group-file', config_path, testcase_path.name], tmp_path
    )
    proc.communicate()
    assert proc.returncode == 0
    assert (
        copy_path.read_text()
        == """
        int foo() {
        }
        """
    )
    assert_subprocess_tmpdir_empty(tmp_path)


def test_apply_hints(tmp_path: Path):
    """Test the application of hints via the --action=apply-hints mode."""
    hints_path = tmp_path / 'hints.jsonl'
    hints_path.write_text(
        """{"format": "cvise_hints_v0"}
        []
        {"p": [{"l": 0, "r": 1}]}
        {"p": [{"l": 1, "r": 2}]}
        {"p": [{"l": 2, "r": 3}]}
        """
    )

    input_path = tmp_path / 'input.txt'
    input_path.write_text('abcd')

    proc = start_cvise(
        ['--action=apply-hints', '--hints-file', hints_path, '--hint-begin-index=1', '--hint-end-index=3', input_path],
        tmp_path,
    )
    stdout, _ = proc.communicate()
    assert proc.returncode == 0
    assert stdout == 'ad'
    assert_subprocess_tmpdir_empty(tmp_path)


def test_non_ascii(tmp_path: Path):
    testcase_path = tmp_path / 'test.c'
    testcase_path.write_bytes(b"""
        // nonutf\xff
        int foo;
        char *s = "Streichholzsch\xc3\xa4chtelchen";
        """)
    shutil.copy(testcase_path, '.')
    copy_path = Path(testcase_path.name)

    # Also enable diff logging to check it doesn't break on non-unicode.
    proc = start_cvise(['-c', 'gcc -c test.c && grep foo test.c', testcase_path.name, '--print-diff'], tmp_path)
    proc.communicate()

    assert proc.returncode == 0
    # The reduced result may or may not include the trailing line break - this depends on random ordering factors.
    assert copy_path.read_text() in ('int foo;', 'int foo;\n')
    assert_subprocess_tmpdir_empty(tmp_path)


@pytest.mark.skipif(os.name != 'posix', reason='requires POSIX for command-line tools')
def test_non_ascii_interestingness_test(tmp_path: Path):
    """Test no breakage caused by non-UTF-8 characters printed by the interestingness test"""
    check_cvise(
        'blocksort-part.c',
        ['-c', r"printf '\xc3\xa4\xff'; gcc -c blocksort-part.c && grep '\<nextHi\>' blocksort-part.c"],
        ['#define nextHi'],
        tmp_path,
    )

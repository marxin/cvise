import os
from pathlib import Path
import pytest
import shutil
import signal
import stat
import subprocess
import time


def start_cvise(testcase, arguments):
    current = os.path.dirname(__file__)
    binary = os.path.join(current, '../cvise-cli.py')
    shutil.copy(os.path.join(current, 'sources', testcase), '.')
    os.chmod(testcase, 0o644)
    cmd = [binary, testcase] + arguments
    return subprocess.Popen(cmd, encoding='utf8')

def check_cvise(testcase, arguments, expected):
    proc = start_cvise(testcase, arguments)
    proc.communicate()
    assert proc.returncode == 0

    with open(testcase) as f:
        content = f.read()
    assert content in expected
    assert stat.filemode(os.stat(testcase).st_mode) == '-rw-r--r--'

def wait_until_file_created(path: Path):
    while not path.exists():
        time.sleep(0.1)

def test_simple_reduction():
    check_cvise(
        'blocksort-part.c',
        ['-c', 'gcc -c blocksort-part.c && grep nextHi blocksort-part.c'],
        ['#define nextHi', '#define  nextHi'],
    )

@pytest.mark.skipif(os.name != 'posix', reason='requires POSIX for command-line tools')
def test_ctrl_c(tmp_path: Path):
    """Test that Control-C is handled quickly, without waiting for jobs to finish."""
    MAX_SHUTDOWN = 10  # tolerance on C-Vise shutdown to prevent flakiness (normally it's a fraction of a seconds)
    JOB_SLOWNESS = MAX_SHUTDOWN * 2  # make a single job slower than the thresholds

    flag_file = tmp_path / 'flag'

    proc = start_cvise(
        'blocksort-part.c',
        ['-c', f'gcc -c blocksort-part.c && touch {flag_file} && sleep {JOB_SLOWNESS}', '--skip-interestingness-test-check'],
    )
    # to make the test cover the interesting scenario, we wait until C-Vise starts at least one job
    wait_until_file_created(flag_file)

    proc.send_signal(signal.SIGINT)
    try:
        proc.communicate(timeout=MAX_SHUTDOWN)
    except TimeoutError:
        # C-Vise has not quit on time - kill it and fail the test
        proc.kill()
        raise

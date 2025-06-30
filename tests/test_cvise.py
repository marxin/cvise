import os
import shutil
import signal
import stat
import subprocess
import time
import unittest


class TestCvise(unittest.TestCase):
    @classmethod
    def start_cvise(cls, testcase, arguments):
        current = os.path.dirname(__file__)
        binary = os.path.join(current, '../cvise-cli.py')
        shutil.copy(os.path.join(current, 'sources', testcase), '.')
        os.chmod(testcase, 0o644)
        cmd = f'{binary} {testcase} {arguments}'
        return subprocess.Popen(cmd, shell=True, encoding='utf8')

    @classmethod
    def check_cvise(cls, testcase, arguments, expected):
        proc = cls.start_cvise(testcase, arguments)
        proc.communicate()
        assert proc.returncode == 0

        with open(testcase) as f:
            content = f.read()
        assert content in expected
        assert stat.filemode(os.stat(testcase).st_mode) == '-rw-r--r--'

    def test_simple_reduction(self):
        self.check_cvise(
            'blocksort-part.c',
            '-c "gcc -c blocksort-part.c && grep nextHi blocksort-part.c"',
            ['#define nextHi', '#define  nextHi'],
        )

    @unittest.skipUnless(os.name == 'posix', 'requires POSIX')
    def test_ctrl_c(self):
        """Test that Control-C is handled quickly, without waiting for jobs to finish."""
        INIT_DELAY = 1  # semi-arbitrary delay to let the C-Vise start doing actual work
        MAX_SHUTDOWN = 10  # tolerance on C-Vise shutdown to prevent flakiness (normally it's fractions of seconds)
        JOB_SLOWNESS = (INIT_DELAY + MAX_SHUTDOWN) * 2  # make a single job slower than the thresholds

        proc = self.start_cvise(
            'blocksort-part.c',
            f'-c "gcc -c blocksort-part.c && sleep {JOB_SLOWNESS}" --skip-interestingness-test-check',
        )
        time.sleep(INIT_DELAY)

        proc.send_signal(signal.SIGINT)
        proc.communicate(timeout=MAX_SHUTDOWN)
        # no assertions needed - a slow shutdown would manifest as a TimeoutExpired exception

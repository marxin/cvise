import logging
import os
import random
import shutil
import signal
import stat
import subprocess
import time
import unittest


def get_available_cores():
    import psutil
    try:
        # try to detect only physical cores, ignore HyperThreading
        # in order to speed up parallel execution
        core_count = psutil.cpu_count(logical=False)
        if not core_count:
            core_count = psutil.cpu_count(logical=True)
        # respect affinity
        try:
            affinity = len(psutil.Process().cpu_affinity())
            assert affinity >= 1
        except AttributeError:
            return core_count

        if core_count:
            core_count = min(core_count, affinity)
        else:
            core_count = affinity
        return core_count
    except NotImplementedError:
        return 1


class TestCvise(unittest.TestCase):
    @classmethod
    def start_cvise(cls, testcase, arguments):
        current = os.path.dirname(__file__)
        binary = os.path.join(current, '../cvise-cli.py')
        shutil.copy(os.path.join(current, 'sources', testcase), '.')
        os.chmod(testcase, 0o644)
        cmd = [binary, testcase] + arguments
        return subprocess.Popen(cmd, encoding='utf8')

    @classmethod
    def check_cvise(cls, testcase, arguments, expected):
        proc = cls.start_cvise(testcase, arguments)
        proc.communicate()
        assert proc.returncode == 0

        with open(testcase) as f:
            content = f.read()
        assert content in expected
        assert stat.filemode(os.stat(testcase).st_mode) == '-rw-r--r--'

    # def test_simple_reduction(self):
    #     self.check_cvise(
    #         'blocksort-part.c',
    #         '-c "gcc -c blocksort-part.c && grep nextHi blocksort-part.c"',
    #         ['#define nextHi', '#define  nextHi'],
    #     )

    @unittest.skipUnless(os.name == 'posix', 'requires POSIX')
    def test_ctrl_c(self):
        """Test that Control-C is handled quickly, without waiting for jobs to finish."""
        INIT_DELAY = 3  # semi-arbitrary delay to let the C-Vise start doing actual work
        MAX_SHUTDOWN = 10  # tolerance on C-Vise shutdown to prevent flakiness (normally it's fractions of seconds)
        JOB_SLOWNESS = (INIT_DELAY + MAX_SHUTDOWN) * 2  # make a single job slower than the thresholds

        logging.basicConfig(level=logging.DEBUG, force=True)

        init_delay = 0.5 + random.random() * INIT_DELAY
        n = random.randint(1, get_available_cores())
        logging.info(f'init_delay={init_delay} n={n}')
        proc = self.start_cvise(
            'blocksort-part.c',
            ['-c', 'gcc -c blocksort-part.c && sleep {JOB_SLOWNESS}', '--skip-interestingness-test-check', f'--n={n}', '--debug',]
        )
        time.sleep(init_delay)

        logging.info(f'send_signal SIGINT')
        proc.send_signal(signal.SIGINT)
        try:
            proc.communicate(timeout=MAX_SHUTDOWN)
        except TimeoutError:
            # C-Vise not quit on time - kill it and fail the test
            proc.kill()
            raise

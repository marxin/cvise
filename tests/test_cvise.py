import os
import shutil
import stat
import subprocess
import unittest


class TestCvise(unittest.TestCase):

    @classmethod
    def check_cvise(cls, testcase, arguments, expected):
        current = os.path.dirname(__file__)
        binary = os.path.join(current, '../cvise.py')
        shutil.copy(os.path.join(current, 'sources', testcase), '.')
        os.chmod(testcase, 0o644)
        cmd = f'{binary} {testcase} {arguments}'
        subprocess.check_output(cmd, shell=True, encoding='utf8')
        with open(testcase) as f:
            content = f.read()
        assert content in expected
        assert stat.filemode(os.stat(testcase).st_mode) == '-rw-r--r--'

    def test_simple_reduction(self):
        self.check_cvise('blocksort-part.c', '-c "gcc -c blocksort-part.c && grep nextHi blocksort-part.c"',
                         ['#define nextHi', '#define  nextHi '])

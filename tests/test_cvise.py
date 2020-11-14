import os
import shutil
import subprocess
import unittest

class TestCvise(unittest.TestCase):

    @classmethod
    def check_cvise(cls, testcase, arguments, expected):
        current = os.path.dirname(__file__)
        binary = os.path.join(current, '../cvise.py')
        shutil.copy(os.path.join(current, 'sources', testcase), '.')
        cmd = '%s %s %s' % (binary, testcase, arguments)
        subprocess.check_output(cmd, shell=True, encoding='utf8')
        assert open(testcase).read() == expected

    def test_simple_reduction(self):
        self.check_cvise('blocksort-part.c', '-c "gcc -c blocksort-part.c && grep nextHi blocksort-part.c"', '#define nextHi')

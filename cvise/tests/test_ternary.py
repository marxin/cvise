import os
from pathlib import Path
import tempfile
import unittest

from cvise.passes.abstract import PassResult
from cvise.passes.ternary import TernaryPass


class TernaryBTestCase(unittest.TestCase):
    def setUp(self):
        self.pass_ = TernaryPass('b')

    def test_b(self):
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as tmp_file:
            tmp_file.write('int res = a ? b : c;\n')
            tmp_path = Path(tmp_file.name)

        state = self.pass_.new(tmp_path)
        (_, state) = self.pass_.transform(tmp_path, state, None)

        variant = tmp_path.read_text()

        tmp_path.unlink()

        self.assertEqual(variant, 'int res = b;\n')

    def test_parens(self):
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as tmp_file:
            tmp_file.write('int res = (a != 0) ? (b + 5) : c;\n')
            tmp_path = Path(tmp_file.name)

        state = self.pass_.new(tmp_path)
        (_, state) = self.pass_.transform(tmp_path, state, None)

        variant = tmp_path.read_text()

        tmp_path.unlink()

        self.assertEqual(variant, 'int res = (b + 5);\n')

    def test_all_b(self):
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as tmp_file:
            tmp_file.write('// no ? match :\nint res = a ? (ba ? bb : bc) : c\nint sec = t ? u : v\n')
            tmp_path = Path(tmp_file.name)

        state = self.pass_.new(tmp_path)
        (result, state) = self.pass_.transform(tmp_path, state, None)

        while result == PassResult.OK:
            state = self.pass_.advance_on_success(tmp_path, state)
            (result, state) = self.pass_.transform(tmp_path, state, None)

        variant = tmp_path.read_text()

        tmp_path.unlink()

        self.assertEqual(variant, '// match res = (bb)\nint sec = u\n')

    def test_all_b_2(self):
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as tmp_file:
            tmp_file.write('// no ? match :!\nint res = a ? (ba ? bb : bc) : c\nint sec = t ? u : v\n')
            tmp_path = Path(tmp_file.name)

        state = self.pass_.new(tmp_path)
        (result, state) = self.pass_.transform(tmp_path, state, None)

        iteration = 0

        while result == PassResult.OK and iteration < 5:
            state = self.pass_.advance_on_success(tmp_path, state)
            (result, state) = self.pass_.transform(tmp_path, state, None)
            iteration += 1

        variant = tmp_path.read_text()

        tmp_path.unlink()

        self.assertEqual(iteration, 3)
        self.assertEqual(variant, '// no ? match :!\nint res = (bb)\nint sec = u\n')

    def test_no_success(self):
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as tmp_file:
            tmp_file.write('// no ? match :\nint res = a ? (ba ? bb : bc) : c\nint sec = t ? u : v\n')
            tmp_path = Path(tmp_file.name)

        state = self.pass_.new(tmp_path)
        (result, state) = self.pass_.transform(tmp_path, state, None)

        iteration = 0

        while result == PassResult.OK and iteration < 6:
            tmp_path.write_text('// no ? match :\nint res = a ? (ba ? bb : bc) : c\nint sec = t ? u : v\n')

            state = self.pass_.advance(tmp_path, state)
            (result, state) = self.pass_.transform(tmp_path, state, None)
            iteration += 1

        tmp_path.unlink()

        self.assertEqual(iteration, 4)


class TernaryCTestCase(unittest.TestCase):
    def setUp(self):
        self.pass_ = TernaryPass('c')

    def test_c(self):
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as tmp_file:
            tmp_file.write('int res = a ? b : c;\n')
            tmp_path = Path(tmp_file.name)

        state = self.pass_.new(tmp_path)
        (_, state) = self.pass_.transform(tmp_path, state, None)

        variant = tmp_path.read_text()

        tmp_path.unlink()

        self.assertEqual(variant, 'int res = c;\n')

import tempfile
import unittest
from pathlib import Path

from cvise.passes.abstract import PassResult
from cvise.passes.ternary import TernaryPass


class TernaryBTestCase(unittest.TestCase):
    def setUp(self):
        # TODO: use enterContext() once Python 3.11 is the oldest supported release
        self.tmp_dir_obj = tempfile.TemporaryDirectory()
        self.tmp_dir: Path = Path(self.tmp_dir_obj.name)
        self.input_path: Path = self.tmp_dir / 'test_case'
        self.pass_ = TernaryPass('b')

    def tearDown(self):
        self.tmp_dir_obj.cleanup()

    def test_b(self):
        self.input_path.write_text('int res = a ? b : c;\n')

        state = self.pass_.new(self.input_path)
        (_, state) = self.pass_.transform(self.input_path, state, None)

        variant = self.input_path.read_text()
        self.assertEqual(variant, 'int res = b;\n')

    def test_parens(self):
        self.input_path.write_text('int res = (a != 0) ? (b + 5) : c;\n')

        state = self.pass_.new(self.input_path)
        (_, state) = self.pass_.transform(self.input_path, state, None)

        variant = self.input_path.read_text()
        self.assertEqual(variant, 'int res = (b + 5);\n')

    def test_all_b(self):
        self.input_path.write_text('// no ? match :\nint res = a ? (ba ? bb : bc) : c\nint sec = t ? u : v\n')

        state = self.pass_.new(self.input_path)
        (result, state) = self.pass_.transform(self.input_path, state, None)

        while result == PassResult.OK:
            state = self.pass_.advance_on_success(self.input_path, state)
            (result, state) = self.pass_.transform(self.input_path, state, None)

        variant = self.input_path.read_text()
        self.assertEqual(variant, '// match res = (bb)\nint sec = u\n')

    def test_all_b_2(self):
        self.input_path.write_text('// no ? match :!\nint res = a ? (ba ? bb : bc) : c\nint sec = t ? u : v\n')

        state = self.pass_.new(self.input_path)
        (result, state) = self.pass_.transform(self.input_path, state, None)

        iteration = 0

        while result == PassResult.OK and iteration < 5:
            state = self.pass_.advance_on_success(self.input_path, state)
            (result, state) = self.pass_.transform(self.input_path, state, None)
            iteration += 1

        variant = self.input_path.read_text()
        self.assertEqual(iteration, 3)
        self.assertEqual(variant, '// no ? match :!\nint res = (bb)\nint sec = u\n')

    def test_no_success(self):
        self.input_path.write_text('// no ? match :\nint res = a ? (ba ? bb : bc) : c\nint sec = t ? u : v\n')

        state = self.pass_.new(self.input_path)
        (result, state) = self.pass_.transform(self.input_path, state, None)

        iteration = 0

        while result == PassResult.OK and iteration < 6:
            self.input_path.write_text('// no ? match :\nint res = a ? (ba ? bb : bc) : c\nint sec = t ? u : v\n')

            state = self.pass_.advance(self.input_path, state)
            (result, state) = self.pass_.transform(self.input_path, state, None)
            iteration += 1
        self.assertEqual(iteration, 4)


class TernaryCTestCase(unittest.TestCase):
    def setUp(self):
        # TODO: use enterContext() once Python 3.11 is the oldest supported release
        self.tmp_dir_obj = tempfile.TemporaryDirectory()
        self.tmp_dir: Path = Path(self.tmp_dir_obj.name)
        self.input_path: Path = self.tmp_dir / 'test_case'
        self.pass_ = TernaryPass('c')

    def tearDown(self):
        self.tmp_dir_obj.cleanup()

    def test_c(self):
        self.input_path.write_text('int res = a ? b : c;\n')

        state = self.pass_.new(self.input_path)
        (_, state) = self.pass_.transform(self.input_path, state, None)

        variant = self.input_path.read_text()
        self.assertEqual(variant, 'int res = c;\n')

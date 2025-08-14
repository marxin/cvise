from pathlib import Path
import tempfile
import unittest

from cvise.passes.abstract import PassResult
from cvise.passes.ints import IntsPass


class IntsATestCase(unittest.TestCase):
    def setUp(self):
        self.pass_ = IntsPass('a')

    def test_a(self):
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as tmp_file:
            tmp_file.write('Compute 123L + 0x456 + 0789!\n')
            tmp_path = Path(tmp_file.name)

        state = self.pass_.new(tmp_path)
        (_, state) = self.pass_.transform(tmp_path, state, None)

        variant = tmp_path.read_text()

        tmp_path.unlink()

        self.assertEqual(variant, 'Compute 123L + 0x56 + 0789!\n')

    def test_success_a(self):
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as tmp_file:
            tmp_file.write('Compute 123L + 0x456 + 0789!\n')
            tmp_path = Path(tmp_file.name)

        state = self.pass_.new(tmp_path)
        (result, state) = self.pass_.transform(tmp_path, state, None)

        iteration = 1
        while result == PassResult.OK and iteration < 10:
            state = self.pass_.advance_on_success(tmp_path, state)
            if state is None:
                break
            (result, state) = self.pass_.transform(tmp_path, state, None)
            iteration += 1

        variant = tmp_path.read_text()

        tmp_path.unlink()

        self.assertEqual(iteration, 4)
        self.assertEqual(variant, 'Compute 3L + 0x6 + 0789!\n')

    def test_no_success_a(self):
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as tmp_file:
            tmp_file.write('Compute 123L + 0x456 + 0789!\n')
            tmp_path = Path(tmp_file.name)

        state = self.pass_.new(tmp_path)
        (result, state) = self.pass_.transform(tmp_path, state, None)

        iteration = 1

        while result == PassResult.OK and iteration < 10:
            tmp_path.write_text('Compute 123L + 0x456 + 0789!\n')

            state = self.pass_.advance(tmp_path, state)
            if state is None:
                break
            (result, state) = self.pass_.transform(tmp_path, state, None)
            iteration += 1

        tmp_path.unlink()

        self.assertEqual(iteration, 2)


class IntsBTestCase(unittest.TestCase):
    def setUp(self):
        self.pass_ = IntsPass('b')

    def test_b(self):
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as tmp_file:
            tmp_file.write('Compute 123L + 0x456 + 0789!\n')
            tmp_path = Path(tmp_file.name)

        state = self.pass_.new(tmp_path)
        (_, state) = self.pass_.transform(tmp_path, state, None)

        variant = tmp_path.read_text()

        tmp_path.unlink()

        self.assertEqual(variant, 'Compute 123L + 456 + 0789!\n')


class IntsCTestCase(unittest.TestCase):
    def setUp(self):
        self.pass_ = IntsPass('c')

    def test_c(self):
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as tmp_file:
            tmp_file.write('Compute 123L + 0x456 + 0789!\n')
            tmp_path = Path(tmp_file.name)

        state = self.pass_.new(tmp_path)
        (_, state) = self.pass_.transform(tmp_path, state, None)

        variant = tmp_path.read_text()

        tmp_path.unlink()

        self.assertEqual(variant, 'Compute 123 + 0x456 + 0789!\n')


class IntsDTestCase(unittest.TestCase):
    def setUp(self):
        self.pass_ = IntsPass('d')

    def test_d(self):
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as tmp_file:
            tmp_file.write('Compute 123L + 0x456 + 0789!\n')
            tmp_path = Path(tmp_file.name)

        state = self.pass_.new(tmp_path)
        (_, state) = self.pass_.transform(tmp_path, state, None)

        variant = tmp_path.read_text()

        tmp_path.unlink()

        self.assertEqual(variant, 'Compute 123L + 1110 + 0789!\n')

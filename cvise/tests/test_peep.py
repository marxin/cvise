from pathlib import Path
import tempfile
import unittest

from cvise.passes.peep import PeepPass
from cvise.tests.testabstract import iterate_pass


class PeepATestCase(unittest.TestCase):
    def setUp(self):
        self.pass_ = PeepPass('a')

    def test_a_1(self):
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as tmp_file:
            tmp_file.write("<That's a small test> whether the transformation works!\n")
            tmp_path = Path(tmp_file.name)

        iterate_pass(self.pass_, tmp_path)

        variant = tmp_path.read_text()

        tmp_path.unlink()

        self.assertEqual(variant, ' whether the transformation works\n')

    def test_a_2(self):
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as tmp_file:
            tmp_file.write("{That's a small test} whether the transformation works!\n")
            tmp_path = Path(tmp_file.name)

        iterate_pass(self.pass_, tmp_path)

        variant = tmp_path.read_text()

        tmp_path.unlink()

        self.assertEqual(variant, ' whether the transformation works\n')

    def test_a_3(self):
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as tmp_file:
            tmp_file.write('namespace cvise {Some more content} which is not interesting!\n')
            tmp_path = Path(tmp_file.name)

        iterate_pass(self.pass_, tmp_path)

        variant = tmp_path.read_text()

        tmp_path.unlink()

        self.assertEqual(variant, ' which is not interesting\n')

    def test_a_4(self):
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as tmp_file:
            tmp_file.write('namespace {Some more content} which is not interesting!\n')
            tmp_path = Path(tmp_file.name)

        iterate_pass(self.pass_, tmp_path)

        variant = tmp_path.read_text()

        tmp_path.unlink()

        self.assertEqual(variant, ' which is not interesting\n')

    def test_a_5(self):
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as tmp_file:
            tmp_file.write('struct test_t {} test;\n')
            tmp_path = Path(tmp_file.name)

        iterate_pass(self.pass_, tmp_path)

        variant = tmp_path.read_text()

        tmp_path.unlink()

        self.assertEqual(variant, ' test\n')

    def test_success_a(self):
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as tmp_file:
            tmp_file.write('struct test_t {int a;} foo = {1};\n')
            tmp_path = Path(tmp_file.name)

        state = self.pass_.new(tmp_path)
        (_result, state) = self.pass_.transform(tmp_path, state, None)

        iterate_pass(self.pass_, tmp_path)

        variant = tmp_path.read_text()

        tmp_path.unlink()

        self.assertEqual(variant, ' foo \n')


class PeepBTestCase(unittest.TestCase):
    def setUp(self):
        self.pass_ = PeepPass('b')

    def test_b_1(self):
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as tmp_file:
            tmp_file.write('struct test_t {} test;\n')
            tmp_path = Path(tmp_file.name)

        iterate_pass(self.pass_, tmp_path)

        variant = tmp_path.read_text()

        tmp_path.unlink()

        self.assertEqual(variant, 'struct  {} ;\n')

    def test_success_b(self):
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as tmp_file:
            tmp_file.write('struct test_t {int a;} foo = {1};\n')
            tmp_path = Path(tmp_file.name)

        state = self.pass_.new(tmp_path)
        (_result, state) = self.pass_.transform(tmp_path, state, None)

        iterate_pass(self.pass_, tmp_path)

        variant = tmp_path.read_text()

        tmp_path.unlink()

        self.assertEqual(variant, 'struct  { ;}  = {};\n')

    def test_infinite_loop(self):
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as tmp_file:
            tmp_file.write(',0,')
            tmp_path = Path(tmp_file.name)

        state = self.pass_.new(tmp_path)
        (_result, state) = self.pass_.transform(tmp_path, state, None)

        iterate_pass(self.pass_, tmp_path)

        variant = tmp_path.read_text()

        tmp_path.unlink()

        self.assertEqual(variant, ',,')


class PeepCTestCase(unittest.TestCase):
    def setUp(self):
        self.pass_ = PeepPass('c')

    def test_c_1(self):
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as tmp_file:
            tmp_file.write('while   (a == b)\n{\n    int a = 4;\n    short b = 5;\n    break;\n}\n\nulong c = 18;\n')
            tmp_path = Path(tmp_file.name)

        state = self.pass_.new(tmp_path)
        (_, state) = self.pass_.transform(tmp_path, state, None)

        variant = tmp_path.read_text()

        tmp_path.unlink()

        self.assertEqual(variant, '{\n    int a = 4;\n    short b = 5;\n    \n}\n\nulong c = 18;\n')

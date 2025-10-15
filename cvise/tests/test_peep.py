import tempfile
import unittest
from pathlib import Path

from cvise.passes.peep import PeepPass
from cvise.tests.testabstract import iterate_pass


class PeepATestCase(unittest.TestCase):
    def setUp(self):
        # TODO: use enterContext() once Python 3.11 is the oldest supported release
        self.tmp_dir_obj = tempfile.TemporaryDirectory()
        self.tmp_dir: Path = Path(self.tmp_dir_obj.name)
        self.input_path: Path = self.tmp_dir / 'test_case'
        self.pass_ = PeepPass('a')

    def tearDown(self):
        self.tmp_dir_obj.cleanup()

    def test_a_1(self):
        self.input_path.write_text("<That's a small test> whether the transformation works!\n")

        iterate_pass(self.pass_, self.input_path)

        variant = self.input_path.read_text()
        self.assertEqual(variant, ' whether the transformation works\n')

    def test_a_2(self):
        self.input_path.write_text("{That's a small test} whether the transformation works!\n")

        iterate_pass(self.pass_, self.input_path)

        variant = self.input_path.read_text()
        self.assertEqual(variant, ' whether the transformation works\n')

    def test_a_3(self):
        self.input_path.write_text('namespace cvise {Some more content} which is not interesting!\n')

        iterate_pass(self.pass_, self.input_path)

        variant = self.input_path.read_text()
        self.assertEqual(variant, ' which is not interesting\n')

    def test_a_4(self):
        self.input_path.write_text('namespace {Some more content} which is not interesting!\n')

        iterate_pass(self.pass_, self.input_path)

        variant = self.input_path.read_text()
        self.assertEqual(variant, ' which is not interesting\n')

    def test_a_5(self):
        self.input_path.write_text('struct test_t {} test;\n')

        iterate_pass(self.pass_, self.input_path)

        variant = self.input_path.read_text()
        self.assertEqual(variant, ' test\n')

    def test_success_a(self):
        self.input_path.write_text('struct test_t {int a;} foo = {1};\n')

        state = self.pass_.new(self.input_path)
        (_result, state) = self.pass_.transform(self.input_path, state, None)

        iterate_pass(self.pass_, self.input_path)

        variant = self.input_path.read_text()
        self.assertEqual(variant, ' foo \n')


class PeepBTestCase(unittest.TestCase):
    def setUp(self):
        # TODO: use enterContext() once Python 3.11 is the oldest supported release
        self.tmp_dir_obj = tempfile.TemporaryDirectory()
        self.tmp_dir: Path = Path(self.tmp_dir_obj.name)
        self.input_path: Path = self.tmp_dir / 'test_case'
        self.pass_ = PeepPass('b')

    def tearDown(self):
        self.tmp_dir_obj.cleanup()

    def test_b_1(self):
        self.input_path.write_text('struct test_t {} test;\n')

        iterate_pass(self.pass_, self.input_path)

        variant = self.input_path.read_text()
        self.assertEqual(variant, 'struct  {} ;\n')

    def test_success_b(self):
        self.input_path.write_text('struct test_t {int a;} foo = {1};\n')

        state = self.pass_.new(self.input_path)
        (_result, state) = self.pass_.transform(self.input_path, state, None)

        iterate_pass(self.pass_, self.input_path)

        variant = self.input_path.read_text()
        self.assertEqual(variant, 'struct  { ;}  = {};\n')

    def test_infinite_loop(self):
        self.input_path.write_text(',0,')

        state = self.pass_.new(self.input_path)
        (_result, state) = self.pass_.transform(self.input_path, state, None)

        iterate_pass(self.pass_, self.input_path)

        variant = self.input_path.read_text()
        self.assertEqual(variant, ',,')


class PeepCTestCase(unittest.TestCase):
    def setUp(self):
        # TODO: use enterContext() once Python 3.11 is the oldest supported release
        self.tmp_dir_obj = tempfile.TemporaryDirectory()
        self.tmp_dir: Path = Path(self.tmp_dir_obj.name)
        self.input_path: Path = self.tmp_dir / 'test_case'
        self.pass_ = PeepPass('c')

    def tearDown(self):
        self.tmp_dir_obj.cleanup()

    def test_c_1(self):
        self.input_path.write_text(
            'while   (a == b)\n{\n    int a = 4;\n    short b = 5;\n    break;\n}\n\nulong c = 18;\n'
        )

        state = self.pass_.new(self.input_path)
        (_, state) = self.pass_.transform(self.input_path, state, None)

        variant = self.input_path.read_text()
        self.assertEqual(variant, '{\n    int a = 4;\n    short b = 5;\n    \n}\n\nulong c = 18;\n')

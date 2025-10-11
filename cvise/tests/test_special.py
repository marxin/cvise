from pathlib import Path
import tempfile
import unittest

from cvise.passes.special import SpecialPass
from cvise.tests.testabstract import iterate_pass


class SpecialATestCase(unittest.TestCase):
    def setUp(self):
        # TODO: use enterContext() once Python 3.11 is the oldest supported release
        self.tmp_dir_obj = tempfile.TemporaryDirectory()
        self.tmp_dir: Path = Path(self.tmp_dir_obj.name)
        self.input_path: Path = self.tmp_dir / 'test_case'
        self.pass_ = SpecialPass('a')

    def tearDown(self):
        self.tmp_dir_obj.cleanup()

    def test_a(self):
        self.input_path.write_text(
            "// Useless comment\ntransparent_crc(g_376.f0, 'g_376.f0', print_hash_value);\ntransparent_crc(g_1194[i].f0, 'g_1194[i].f0', print_hash_value);\nint a = 9;"
        )

        iterate_pass(self.pass_, self.input_path)

        variant = self.input_path.read_text()
        self.assertEqual(
            variant,
            "// Useless comment\nprintf('%d\\n', (int)g_376.f0);\nprintf('%d\\n', (int)g_1194[i].f0);\nint a = 9;",
        )

    def test_success_a(self):
        self.input_path.write_text(
            "// Useless comment\ntransparent_crc(g_376.f0, 'g_376.f0', print_hash_value);\ntransparent_crc(g_1194[i].f0, 'g_1194[i].f0', print_hash_value);\nint a = 9;"
        )

        state = self.pass_.new(self.input_path)
        (_result, state) = self.pass_.transform(self.input_path, state, None)

        iterate_pass(self.pass_, self.input_path)

        variant = self.input_path.read_text()
        self.assertEqual(
            variant,
            "// Useless comment\nprintf('%d\\n', (int)g_376.f0);\nprintf('%d\\n', (int)g_1194[i].f0);\nint a = 9;",
        )


class SpecialBTestCase(unittest.TestCase):
    def setUp(self):
        # TODO: use enterContext() once Python 3.11 is the oldest supported release
        self.tmp_dir_obj = tempfile.TemporaryDirectory()
        self.tmp_dir: Path = Path(self.tmp_dir_obj.name)
        self.input_path: Path = self.tmp_dir / 'test_case'
        self.pass_ = SpecialPass('b')

    def tearDown(self):
        self.tmp_dir_obj.cleanup()

    def test_b(self):
        self.input_path.write_text("void foo(){} extern 'C' {int a;}; a = 9;\n")

        state = self.pass_.new(self.input_path)
        (_, state) = self.pass_.transform(self.input_path, state, None)

        variant = self.input_path.read_text()
        self.assertEqual(variant, 'void foo(){}  {int a;}; a = 9;\n')


class SpecialCTestCase(unittest.TestCase):
    def setUp(self):
        # TODO: use enterContext() once Python 3.11 is the oldest supported release
        self.tmp_dir_obj = tempfile.TemporaryDirectory()
        self.tmp_dir: Path = Path(self.tmp_dir_obj.name)
        self.input_path: Path = self.tmp_dir / 'test_case'
        self.pass_ = SpecialPass('c')

    def tearDown(self):
        self.tmp_dir_obj.cleanup()

    def test_c(self):
        self.input_path.write_text("void foo(){} extern 'C++' {int a;}; a = 9;\n")

        state = self.pass_.new(self.input_path)
        (_, state) = self.pass_.transform(self.input_path, state, None)

        variant = self.input_path.read_text()
        self.assertEqual(variant, 'void foo(){}  {int a;}; a = 9;\n')

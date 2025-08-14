from pathlib import Path
import tempfile
import unittest

from cvise.passes.special import SpecialPass
from cvise.tests.testabstract import iterate_pass


class SpecialATestCase(unittest.TestCase):
    def setUp(self):
        self.pass_ = SpecialPass('a')

    def test_a(self):
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as tmp_file:
            tmp_file.write(
                "// Useless comment\ntransparent_crc(g_376.f0, 'g_376.f0', print_hash_value);\ntransparent_crc(g_1194[i].f0, 'g_1194[i].f0', print_hash_value);\nint a = 9;"
            )
            tmp_path = Path(tmp_file.name)

        iterate_pass(self.pass_, tmp_path)

        variant = tmp_path.read_text()

        tmp_path.unlink()

        self.assertEqual(
            variant,
            "// Useless comment\nprintf('%d\\n', (int)g_376.f0);\nprintf('%d\\n', (int)g_1194[i].f0);\nint a = 9;",
        )

    def test_success_a(self):
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as tmp_file:
            tmp_file.write(
                "// Useless comment\ntransparent_crc(g_376.f0, 'g_376.f0', print_hash_value);\ntransparent_crc(g_1194[i].f0, 'g_1194[i].f0', print_hash_value);\nint a = 9;"
            )
            tmp_path = Path(tmp_file.name)

        state = self.pass_.new(tmp_path)
        (_result, state) = self.pass_.transform(tmp_path, state, None)

        iterate_pass(self.pass_, tmp_path)

        variant = tmp_path.read_text()

        tmp_path.unlink()

        self.assertEqual(
            variant,
            "// Useless comment\nprintf('%d\\n', (int)g_376.f0);\nprintf('%d\\n', (int)g_1194[i].f0);\nint a = 9;",
        )


class SpecialBTestCase(unittest.TestCase):
    def setUp(self):
        self.pass_ = SpecialPass('b')

    def test_b(self):
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as tmp_file:
            tmp_file.write("void foo(){} extern 'C' {int a;}; a = 9;\n")
            tmp_path = Path(tmp_file.name)

        state = self.pass_.new(tmp_path)
        (_, state) = self.pass_.transform(tmp_path, state, None)

        variant = tmp_path.read_text()

        tmp_path.unlink()

        self.assertEqual(variant, 'void foo(){}  {int a;}; a = 9;\n')


class SpecialCTestCase(unittest.TestCase):
    def setUp(self):
        self.pass_ = SpecialPass('c')

    def test_c(self):
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as tmp_file:
            tmp_file.write("void foo(){} extern 'C++' {int a;}; a = 9;\n")
            tmp_path = Path(tmp_file.name)

        state = self.pass_.new(tmp_path)
        (_, state) = self.pass_.transform(tmp_path, state, None)

        variant = tmp_path.read_text()

        tmp_path.unlink()

        self.assertEqual(variant, 'void foo(){}  {int a;}; a = 9;\n')

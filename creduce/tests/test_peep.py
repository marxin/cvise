import os
import tempfile
import unittest

from creduce.tests.testabstract import iterate_pass
from creduce.passes.abstract import PassResult
from ..passes import PeepPass

class PeepATestCase(unittest.TestCase):
    def setUp(self):
        self.pass_ = PeepPass("a")

    def test_a_1(self):
        with tempfile.NamedTemporaryFile(mode="w", delete=False) as tmp_file:
            tmp_file.write("<That's a small test> whether the transformation works!\n")

        iterate_pass(self.pass_, tmp_file.name)

        with open(tmp_file.name) as variant_file:
            variant = variant_file.read()

        os.unlink(tmp_file.name)

        self.assertEqual(variant, " whether the transformation works\n")

    def test_a_2(self):
        with tempfile.NamedTemporaryFile(mode="w", delete=False) as tmp_file:
            tmp_file.write("{That's a small test} whether the transformation works!\n")

        iterate_pass(self.pass_, tmp_file.name)

        with open(tmp_file.name) as variant_file:
            variant = variant_file.read()

        os.unlink(tmp_file.name)

        self.assertEqual(variant, " whether the transformation works\n")

    def test_a_3(self):
        with tempfile.NamedTemporaryFile(mode="w", delete=False) as tmp_file:
            tmp_file.write("namespace creduce {Some more content} which is not interesting!\n")

        iterate_pass(self.pass_, tmp_file.name)

        with open(tmp_file.name) as variant_file:
            variant = variant_file.read()

        os.unlink(tmp_file.name)

        self.assertEqual(variant, " which is not interesting\n")

    def test_a_4(self):
        with tempfile.NamedTemporaryFile(mode="w", delete=False) as tmp_file:
            tmp_file.write("namespace {Some more content} which is not interesting!\n")

        iterate_pass(self.pass_, tmp_file.name)

        with open(tmp_file.name) as variant_file:
            variant = variant_file.read()

        os.unlink(tmp_file.name)

        self.assertEqual(variant, " which is not interesting\n")

    def test_a_5(self):
        with tempfile.NamedTemporaryFile(mode="w", delete=False) as tmp_file:
            tmp_file.write("struct test_t {} test;\n")

        iterate_pass(self.pass_, tmp_file.name)

        with open(tmp_file.name) as variant_file:
            variant = variant_file.read()

        os.unlink(tmp_file.name)

        self.assertEqual(variant, " test\n")

    def test_success_a(self):
        with tempfile.NamedTemporaryFile(mode="w", delete=False) as tmp_file:
            tmp_file.write("struct test_t {int a;} foo = {1};\n")

        state = self.pass_.new(tmp_file.name)
        (result, state) = self.pass_.transform(tmp_file.name, state)

        iterate_pass(self.pass_, tmp_file.name)

        with open(tmp_file.name) as variant_file:
            variant = variant_file.read()

        os.unlink(tmp_file.name)

        self.assertEqual(variant, " foo \n")

class PeepBTestCase(unittest.TestCase):
    def setUp(self):
        self.pass_ = PeepPass("b")

    def test_b_1(self):
        with tempfile.NamedTemporaryFile(mode="w", delete=False) as tmp_file:
            tmp_file.write("struct test_t {} test;\n")

        iterate_pass(self.pass_, tmp_file.name)

        with open(tmp_file.name) as variant_file:
            variant = variant_file.read()

        os.unlink(tmp_file.name)

        self.assertEqual(variant, "struct  {} ;\n")

    def test_success_b(self):
        with tempfile.NamedTemporaryFile(mode="w", delete=False) as tmp_file:
            tmp_file.write("struct test_t {int a;} foo = {1};\n")

        state = self.pass_.new(tmp_file.name)
        (result, state) = self.pass_.transform(tmp_file.name, state)

        iterate_pass(self.pass_, tmp_file.name)

        with open(tmp_file.name) as variant_file:
            variant = variant_file.read()

        os.unlink(tmp_file.name)

        self.assertEqual(variant, "struct  { ;}  = {};\n")

    def test_infinite_loop(self):
        with tempfile.NamedTemporaryFile(mode="w", delete=False) as tmp_file:
            tmp_file.write(",0,")

        state = self.pass_.new(tmp_file.name)
        (result, state) = self.pass_.transform(tmp_file.name, state)

        iterate_pass(self.pass_, tmp_file.name)

        with open(tmp_file.name) as variant_file:
            variant = variant_file.read()

        os.unlink(tmp_file.name)

        self.assertEqual(variant, ",,")

class PeepCTestCase(unittest.TestCase):
    def setUp(self):
        self.pass_ = PeepPass("c")

    def test_c_1(self):
        with tempfile.NamedTemporaryFile(mode="w", delete=False) as tmp_file:
            tmp_file.write("while   (a == b)\n{\n    int a = 4;\n    short b = 5;\n    break;\n}\n\nulong c = 18;\n")

        state = self.pass_.new(tmp_file.name)
        (_, state) = self.pass_.transform(tmp_file.name, state)

        with open(tmp_file.name) as variant_file:
            variant = variant_file.read()

        os.unlink(tmp_file.name)

        self.assertEqual(variant, "{\n    int a = 4;\n    short b = 5;\n    \n}\n\nulong c = 18;\n")


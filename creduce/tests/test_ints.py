import os
import tempfile
import unittest

from creduce.passes.abstract import PassResult
from ..passes import IntsPass

class IntsATestCase(unittest.TestCase):
    def setUp(self):
        self.pass_ = IntsPass("a")

    def test_a(self):
        with tempfile.NamedTemporaryFile(mode="w", delete=False) as tmp_file:
            tmp_file.write("Compute 123L + 0x456 + 0789!\n")

        state = self.pass_.new(tmp_file.name)
        (_, state) = self.pass_.transform(tmp_file.name, state)

        with open(tmp_file.name) as variant_file:
            variant = variant_file.read()

        os.unlink(tmp_file.name)

        self.assertEqual(variant, "Compute 123L + 0x56 + 0789!\n")

    def test_success_a(self):
        with tempfile.NamedTemporaryFile(mode="w", delete=False) as tmp_file:
            tmp_file.write("Compute 123L + 0x456 + 0789!\n")

        state = self.pass_.new(tmp_file.name)
        (result, state) = self.pass_.transform(tmp_file.name, state)

        iteration = 1
        while result == PassResult.OK and iteration < 10:
            state = self.pass_.advance_on_success(tmp_file.name, state)
            if state == None:
                break
            (result, state) = self.pass_.transform(tmp_file.name, state)
            iteration += 1

        with open(tmp_file.name) as variant_file:
            variant = variant_file.read()

        os.unlink(tmp_file.name)

        self.assertEqual(iteration, 4)
        self.assertEqual(variant, "Compute 3L + 0x6 + 0789!\n")

    def test_no_success_a(self):
        with tempfile.NamedTemporaryFile(mode="w", delete=False) as tmp_file:
            tmp_file.write("Compute 123L + 0x456 + 0789!\n")

        state = self.pass_.new(tmp_file.name)
        (result, state) = self.pass_.transform(tmp_file.name, state)

        iteration = 1

        while result == PassResult.OK and iteration < 10:
            with tempfile.NamedTemporaryFile(mode="w", delete=False) as tmp_file:
                tmp_file.write("Compute 123L + 0x456 + 0789!\n")

            state = self.pass_.advance(tmp_file.name, state)
            if state == None:
                break
            (result, state) = self.pass_.transform(tmp_file.name, state)
            iteration += 1

        os.unlink(tmp_file.name)

        self.assertEqual(iteration, 2)

class IntsBTestCase(unittest.TestCase):
    def setUp(self):
        self.pass_ = IntsPass("b")

    def test_b(self):
        with tempfile.NamedTemporaryFile(mode="w", delete=False) as tmp_file:
            tmp_file.write("Compute 123L + 0x456 + 0789!\n")

        state = self.pass_.new(tmp_file.name)
        (_, state) = self.pass_.transform(tmp_file.name, state)

        with open(tmp_file.name) as variant_file:
            variant = variant_file.read()

        os.unlink(tmp_file.name)

        self.assertEqual(variant, "Compute 123L + 456 + 0789!\n")

class IntsCTestCase(unittest.TestCase):
    def setUp(self):
        self.pass_ = IntsPass("c")

    def test_c(self):
        with tempfile.NamedTemporaryFile(mode="w", delete=False) as tmp_file:
            tmp_file.write("Compute 123L + 0x456 + 0789!\n")

        state = self.pass_.new(tmp_file.name)
        (_, state) = self.pass_.transform(tmp_file.name, state)

        with open(tmp_file.name) as variant_file:
            variant = variant_file.read()

        os.unlink(tmp_file.name)

        self.assertEqual(variant, "Compute 123 + 0x456 + 0789!\n")

class IntsDTestCase(unittest.TestCase):
    def setUp(self):
        self.pass_ = IntsPass("d")

    def test_d(self):
        with tempfile.NamedTemporaryFile(mode="w", delete=False) as tmp_file:
            tmp_file.write("Compute 123L + 0x456 + 0789!\n")

        state = self.pass_.new(tmp_file.name)
        (_, state) = self.pass_.transform(tmp_file.name, state)

        with open(tmp_file.name) as variant_file:
            variant = variant_file.read()

        os.unlink(tmp_file.name)

        self.assertEqual(variant, "Compute 123L + 1110 + 0789!\n")

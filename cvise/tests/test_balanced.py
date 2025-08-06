import os
from pathlib import Path
import tempfile
import unittest

from cvise.passes.abstract import PassResult
from cvise.passes.balanced import BalancedPass
from cvise.tests.testabstract import collect_all_transforms


class BalancedParensTestCase(unittest.TestCase):
    def setUp(self):
        self.tmp_dir_ = self.enterContext(tempfile.TemporaryDirectory())
        self.pass_ = BalancedPass('parens')

    def test_parens_no_match(self):
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as tmp_file:
            tmp_file.write('This is a simple test!\n')

        state = self.pass_.new(tmp_file.name, tmp_dir=self.tmp_dir_)
        assert state is None

        os.unlink(tmp_file.name)

    def test_parens_simple(self):
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as tmp_file:
            tmp_file.write('This is a (simple) test!\n')

        state = self.pass_.new(tmp_file.name, tmp_dir=self.tmp_dir_)
        (_, state) = self.pass_.transform(tmp_file.name, state, None)

        with open(tmp_file.name) as variant_file:
            variant = variant_file.read()

        os.unlink(tmp_file.name)

        self.assertEqual(variant, 'This is a  test!\n')

    def test_parens_nested_outer(self):
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as tmp_file:
            tmp_file.write('This (is a (simple) test)!\n')

        state = self.pass_.new(tmp_file.name, tmp_dir=self.tmp_dir_)
        (_, state) = self.pass_.transform(tmp_file.name, state, None)

        with open(tmp_file.name) as variant_file:
            variant = variant_file.read()

        os.unlink(tmp_file.name)

        self.assertEqual(variant, 'This !\n')

    def test_parens_nested_inner(self):
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as tmp_file:
            tmp_file.write('This (is a (simple) test)!\n')

        state = self.pass_.new(tmp_file.name, tmp_dir=self.tmp_dir_)
        # Transform failed
        state = self.pass_.advance(tmp_file.name, state)
        (_, state) = self.pass_.transform(tmp_file.name, state, None)

        with open(tmp_file.name) as variant_file:
            variant = variant_file.read()

        os.unlink(tmp_file.name)

        self.assertEqual(variant, 'This (is a  test)!\n')


class BalancedParensOnlyTestCase(unittest.TestCase):
    def setUp(self):
        self.tmp_dir_ = self.enterContext(tempfile.TemporaryDirectory())
        self.pass_ = BalancedPass('parens-only')

    def test_parens_no_match(self):
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as tmp_file:
            tmp_file.write('This is a simple test!\n')

        state = self.pass_.new(tmp_file.name, tmp_dir=self.tmp_dir_)
        assert state is None

        os.unlink(tmp_file.name)

    def test_parens_simple(self):
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as tmp_file:
            tmp_file.write('This is a (simple) test!\n')

        state = self.pass_.new(tmp_file.name, tmp_dir=self.tmp_dir_)
        (_, state) = self.pass_.transform(tmp_file.name, state, None)

        with open(tmp_file.name) as variant_file:
            variant = variant_file.read()

        os.unlink(tmp_file.name)

        self.assertEqual(variant, 'This is a simple test!\n')

    def test_parens_nested_outer(self):
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as tmp_file:
            tmp_file.write('This (is a (simple) test)!\n')

        state = self.pass_.new(tmp_file.name, tmp_dir=self.tmp_dir_)
        all_transforms = collect_all_transforms(self.pass_, state, Path(tmp_file.name))

        os.unlink(tmp_file.name)

        self.assertIn(b'This is a (simple) test!\n', all_transforms)
        self.assertIn(b'This is a (simple) test!\n', all_transforms)
        self.assertIn(b'This is a simple test!\n', all_transforms)

    def test_parens_nested_inner(self):
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as tmp_file:
            tmp_file.write('This (is a (simple) test)!\n')

        state = self.pass_.new(tmp_file.name, tmp_dir=self.tmp_dir_)
        # Transform failed
        state = self.pass_.advance(tmp_file.name, state)
        (_, state) = self.pass_.transform(tmp_file.name, state, None)

        with open(tmp_file.name) as variant_file:
            variant = variant_file.read()

        os.unlink(tmp_file.name)

        self.assertEqual(variant, 'This (is a simple test)!\n')

    def test_parens_nested_both(self):
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as tmp_file:
            tmp_file.write('This (is a (simple) test)!\n')

        state = self.pass_.new(tmp_file.name, tmp_dir=self.tmp_dir_)
        all_transforms = collect_all_transforms(self.pass_, state, Path(tmp_file.name))

        os.unlink(tmp_file.name)

        self.assertIn(b'This (is a simple test)!\n', all_transforms)
        self.assertIn(b'This is a (simple) test!\n', all_transforms)
        self.assertIn(b'This is a simple test!\n', all_transforms)

    def test_parens_nested_all(self):
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as tmp_file:
            tmp_file.write('(This) (is a (((more)) complex) test)!\n')

        state = self.pass_.new(tmp_file.name, tmp_dir=self.tmp_dir_)
        (result, state) = self.pass_.transform(tmp_file.name, state, None)

        iteration = 0

        while result == PassResult.OK:
            state = self.pass_.advance_on_success(tmp_file.name, state)
            if state is None:
                break
            (result, state) = self.pass_.transform(tmp_file.name, state, None)
            iteration += 1

        with open(tmp_file.name) as variant_file:
            variant = variant_file.read()

        os.unlink(tmp_file.name)

        self.assertEqual(variant, 'This is a more complex test!\n')

    def test_parens_nested_no_success(self):
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as tmp_file:
            tmp_file.write('(This) (is a (((more)) complex) test)!\n')

        state = self.pass_.new(tmp_file.name, tmp_dir=self.tmp_dir_)
        all_transforms = collect_all_transforms(self.pass_, state, Path(tmp_file.name))

        os.unlink(tmp_file.name)

        self.assertIn(b'This (is a (((more)) complex) test)!\n', all_transforms)
        self.assertIn(b'(This) (is a ((more) complex) test)!\n', all_transforms)
        self.assertIn(b'(This) (is a ((more)) complex test)!\n', all_transforms)
        self.assertIn(b'(This) is a (((more)) complex) test!\n', all_transforms)
        self.assertIn(b'This is a more complex test!\n', all_transforms)


class BalancedParensInsideTestCase(unittest.TestCase):
    def setUp(self):
        self.tmp_dir_ = self.enterContext(tempfile.TemporaryDirectory())
        self.pass_ = BalancedPass('parens-inside')

    def test_parens_no_match(self):
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as tmp_file:
            tmp_file.write('This is a simple test!\n')

        state = self.pass_.new(tmp_file.name, tmp_dir=self.tmp_dir_)
        assert state is None

        os.unlink(tmp_file.name)

    def test_parens_simple(self):
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as tmp_file:
            tmp_file.write('This is a (simple) test!\n')

        state = self.pass_.new(tmp_file.name, tmp_dir=self.tmp_dir_)
        (_, state) = self.pass_.transform(tmp_file.name, state, None)

        with open(tmp_file.name) as variant_file:
            variant = variant_file.read()

        os.unlink(tmp_file.name)

        self.assertEqual(variant, 'This is a () test!\n')

    def test_parens_nested_outer(self):
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as tmp_file:
            tmp_file.write('This (is a (simple) test)!\n')

        state = self.pass_.new(tmp_file.name, tmp_dir=self.tmp_dir_)
        (_, state) = self.pass_.transform(tmp_file.name, state, None)

        with open(tmp_file.name) as variant_file:
            variant = variant_file.read()

        os.unlink(tmp_file.name)

        self.assertEqual(variant, 'This ()!\n')

    def test_parens_nested_inner(self):
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as tmp_file:
            tmp_file.write('This (is a (simple) test)!\n')

        state = self.pass_.new(tmp_file.name, tmp_dir=self.tmp_dir_)
        # Transform failed
        state = self.pass_.advance(tmp_file.name, state)
        (_, state) = self.pass_.transform(tmp_file.name, state, None)

        with open(tmp_file.name) as variant_file:
            variant = variant_file.read()

        os.unlink(tmp_file.name)

        self.assertEqual(variant, 'This (is a () test)!\n')

    def test_parens_nested_both(self):
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as tmp_file:
            tmp_file.write('This (is a (simple) test)!\n')

        state = self.pass_.new(tmp_file.name, tmp_dir=self.tmp_dir_)
        all_transforms = collect_all_transforms(self.pass_, state, Path(tmp_file.name))

        os.unlink(tmp_file.name)

        self.assertIn(b'This (is a () test)!\n', all_transforms)
        self.assertIn(b'This ()!\n', all_transforms)

    def test_parens_nested_all(self):
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as tmp_file:
            tmp_file.write('(This) (is a (((more)) complex) test)!\n')

        state = self.pass_.new(tmp_file.name, tmp_dir=self.tmp_dir_)
        all_transforms = collect_all_transforms(self.pass_, state, Path(tmp_file.name))

        os.unlink(tmp_file.name)

        self.assertIn(b'() (is a (((more)) complex) test)!\n', all_transforms)
        self.assertIn(b'(This) (is a ((()) complex) test)!\n', all_transforms)
        self.assertIn(b'(This) (is a (() complex) test)!\n', all_transforms)
        self.assertIn(b'(This) (is a () test)!\n', all_transforms)
        self.assertIn(b'(This) ()!\n', all_transforms)
        self.assertIn(b'() ()!\n', all_transforms)

    def test_parens_nested_no_success(self):
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as tmp_file:
            tmp_file.write('(This) (is a (((more)) complex) test)!\n')

        state = self.pass_.new(tmp_file.name, tmp_dir=self.tmp_dir_)
        all_transforms = collect_all_transforms(self.pass_, state, Path(tmp_file.name))

        os.unlink(tmp_file.name)

        self.assertIn(b'() (is a (((more)) complex) test)!\n', all_transforms)
        self.assertIn(b'(This) (is a ((()) complex) test)!\n', all_transforms)
        self.assertIn(b'(This) (is a (() complex) test)!\n', all_transforms)
        self.assertIn(b'(This) (is a () test)!\n', all_transforms)
        self.assertIn(b'(This) ()!\n', all_transforms)
        self.assertIn(b'() ()!\n', all_transforms)

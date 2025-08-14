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
            tmp_path = Path(tmp_file.name)

        state = self.pass_.new(tmp_path, tmp_dir=self.tmp_dir_)
        assert state is None

        tmp_path.unlink()

    def test_parens_simple(self):
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as tmp_file:
            tmp_file.write('This is a (simple) test!\n')
            tmp_path = Path(tmp_file.name)

        state = self.pass_.new(tmp_path, tmp_dir=self.tmp_dir_)
        (_, state) = self.pass_.transform(tmp_path, state, None)

        variant = tmp_path.read_text()

        tmp_path.unlink()

        self.assertEqual(variant, 'This is a  test!\n')

    def test_parens_nested_outer(self):
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as tmp_file:
            tmp_file.write('This (is a (simple) test)!\n')
            tmp_path = Path(tmp_file.name)

        state = self.pass_.new(tmp_path, tmp_dir=self.tmp_dir_)
        (_, state) = self.pass_.transform(tmp_path, state, None)

        variant = tmp_path.read_text()

        tmp_path.unlink()

        self.assertEqual(variant, 'This !\n')

    def test_parens_nested_inner(self):
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as tmp_file:
            tmp_file.write('This (is a (simple) test)!\n')
            tmp_path = Path(tmp_file.name)

        state = self.pass_.new(tmp_path, tmp_dir=self.tmp_dir_)
        # Transform failed
        state = self.pass_.advance(tmp_file.name, state)
        (_, state) = self.pass_.transform(tmp_path, state, None)

        variant = tmp_path.read_text()

        tmp_path.unlink()

        self.assertEqual(variant, 'This (is a  test)!\n')


class BalancedParensOnlyTestCase(unittest.TestCase):
    def setUp(self):
        self.tmp_dir_ = self.enterContext(tempfile.TemporaryDirectory())
        self.pass_ = BalancedPass('parens-only')

    def test_parens_no_match(self):
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as tmp_file:
            tmp_file.write('This is a simple test!\n')
            tmp_path = Path(tmp_file.name)

        state = self.pass_.new(tmp_path, tmp_dir=self.tmp_dir_)
        assert state is None

        tmp_path.unlink()

    def test_parens_simple(self):
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as tmp_file:
            tmp_file.write('This is a (simple) test!\n')
            tmp_path = Path(tmp_file.name)

        state = self.pass_.new(tmp_path, tmp_dir=self.tmp_dir_)
        (_, state) = self.pass_.transform(tmp_path, state, None)

        variant = tmp_path.read_text()

        tmp_path.unlink()

        self.assertEqual(variant, 'This is a simple test!\n')

    def test_parens_nested_outer(self):
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as tmp_file:
            tmp_file.write('This (is a (simple) test)!\n')
            tmp_path = Path(tmp_file.name)

        state = self.pass_.new(tmp_path, tmp_dir=self.tmp_dir_)
        all_transforms = collect_all_transforms(self.pass_, state, tmp_path)

        tmp_path.unlink()

        self.assertIn(b'This is a (simple) test!\n', all_transforms)
        self.assertIn(b'This is a (simple) test!\n', all_transforms)
        self.assertIn(b'This is a simple test!\n', all_transforms)

    def test_parens_nested_inner(self):
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as tmp_file:
            tmp_file.write('This (is a (simple) test)!\n')
            tmp_path = Path(tmp_file.name)

        state = self.pass_.new(tmp_path, tmp_dir=self.tmp_dir_)
        # Transform failed
        state = self.pass_.advance(tmp_file.name, state)
        (_, state) = self.pass_.transform(tmp_path, state, None)

        variant = tmp_path.read_text()

        tmp_path.unlink()

        self.assertEqual(variant, 'This (is a simple test)!\n')

    def test_parens_nested_both(self):
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as tmp_file:
            tmp_file.write('This (is a (simple) test)!\n')
            tmp_path = Path(tmp_file.name)

        state = self.pass_.new(tmp_path, tmp_dir=self.tmp_dir_)
        all_transforms = collect_all_transforms(self.pass_, state, tmp_path)

        tmp_path.unlink()

        self.assertIn(b'This (is a simple test)!\n', all_transforms)
        self.assertIn(b'This is a (simple) test!\n', all_transforms)
        self.assertIn(b'This is a simple test!\n', all_transforms)

    def test_parens_nested_all(self):
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as tmp_file:
            tmp_file.write('(This) (is a (((more)) complex) test)!\n')
            tmp_path = Path(tmp_file.name)

        state = self.pass_.new(tmp_path, tmp_dir=self.tmp_dir_)
        (result, state) = self.pass_.transform(tmp_path, state, None)

        iteration = 0

        while result == PassResult.OK:
            state = self.pass_.advance_on_success(tmp_file.name, state)
            if state is None:
                break
            (result, state) = self.pass_.transform(tmp_path, state, None)
            iteration += 1

        variant = tmp_path.read_text()

        tmp_path.unlink()

        self.assertEqual(variant, 'This is a more complex test!\n')

    def test_parens_nested_no_success(self):
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as tmp_file:
            tmp_file.write('(This) (is a (((more)) complex) test)!\n')
            tmp_path = Path(tmp_file.name)

        state = self.pass_.new(tmp_path, tmp_dir=self.tmp_dir_)
        all_transforms = collect_all_transforms(self.pass_, state, tmp_path)

        tmp_path.unlink()

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
            tmp_path = Path(tmp_file.name)

        state = self.pass_.new(tmp_path, tmp_dir=self.tmp_dir_)
        assert state is None

        tmp_path.unlink()

    def test_parens_simple(self):
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as tmp_file:
            tmp_file.write('This is a (simple) test!\n')
            tmp_path = Path(tmp_file.name)

        state = self.pass_.new(tmp_path, tmp_dir=self.tmp_dir_)
        (_, state) = self.pass_.transform(tmp_path, state, None)

        variant = tmp_path.read_text()

        tmp_path.unlink()

        self.assertEqual(variant, 'This is a () test!\n')

    def test_parens_nested_outer(self):
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as tmp_file:
            tmp_file.write('This (is a (simple) test)!\n')
            tmp_path = Path(tmp_file.name)

        state = self.pass_.new(tmp_path, tmp_dir=self.tmp_dir_)
        (_, state) = self.pass_.transform(tmp_path, state, None)

        variant = tmp_path.read_text()

        tmp_path.unlink()

        self.assertEqual(variant, 'This ()!\n')

    def test_parens_nested_inner(self):
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as tmp_file:
            tmp_file.write('This (is a (simple) test)!\n')
            tmp_path = Path(tmp_file.name)

        state = self.pass_.new(tmp_path, tmp_dir=self.tmp_dir_)
        # Transform failed
        state = self.pass_.advance(tmp_file.name, state)
        (_, state) = self.pass_.transform(tmp_path, state, None)

        variant = tmp_path.read_text()

        tmp_path.unlink()

        self.assertEqual(variant, 'This (is a () test)!\n')

    def test_parens_nested_both(self):
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as tmp_file:
            tmp_file.write('This (is a (simple) test)!\n')
            tmp_path = Path(tmp_file.name)

        state = self.pass_.new(tmp_path, tmp_dir=self.tmp_dir_)
        all_transforms = collect_all_transforms(self.pass_, state, tmp_path)

        tmp_path.unlink()

        self.assertIn(b'This (is a () test)!\n', all_transforms)
        self.assertIn(b'This ()!\n', all_transforms)

    def test_parens_nested_all(self):
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as tmp_file:
            tmp_file.write('(This) (is a (((more)) complex) test)!\n')
            tmp_path = Path(tmp_file.name)

        state = self.pass_.new(tmp_path, tmp_dir=self.tmp_dir_)
        all_transforms = collect_all_transforms(self.pass_, state, tmp_path)

        tmp_path.unlink()

        self.assertIn(b'() (is a (((more)) complex) test)!\n', all_transforms)
        self.assertIn(b'(This) (is a ((()) complex) test)!\n', all_transforms)
        self.assertIn(b'(This) (is a (() complex) test)!\n', all_transforms)
        self.assertIn(b'(This) (is a () test)!\n', all_transforms)
        self.assertIn(b'(This) ()!\n', all_transforms)
        self.assertIn(b'() ()!\n', all_transforms)

    def test_parens_nested_no_success(self):
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as tmp_file:
            tmp_file.write('(This) (is a (((more)) complex) test)!\n')
            tmp_path = Path(tmp_file.name)

        state = self.pass_.new(tmp_path, tmp_dir=self.tmp_dir_)
        all_transforms = collect_all_transforms(self.pass_, state, tmp_path)

        tmp_path.unlink()

        self.assertIn(b'() (is a (((more)) complex) test)!\n', all_transforms)
        self.assertIn(b'(This) (is a ((()) complex) test)!\n', all_transforms)
        self.assertIn(b'(This) (is a (() complex) test)!\n', all_transforms)
        self.assertIn(b'(This) (is a () test)!\n', all_transforms)
        self.assertIn(b'(This) ()!\n', all_transforms)
        self.assertIn(b'() ()!\n', all_transforms)


class BalancedParensToZeroTestCase(unittest.TestCase):
    def setUp(self):
        self.tmp_dir_ = self.enterContext(tempfile.TemporaryDirectory())
        self.pass_ = BalancedPass('parens-to-zero')

    def test_no_match(self):
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as tmp_file:
            tmp_file.write('This is a simple test!\n')
            tmp_path = Path(tmp_file.name)

        state = self.pass_.new(tmp_path, tmp_dir=self.tmp_dir_)
        assert state is None

        tmp_path.unlink()

    def test_simple(self):
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as tmp_file:
            tmp_file.write('int x = (10 + y) / 2;\n')
            tmp_path = Path(tmp_file.name)

        state = self.pass_.new(tmp_path, tmp_dir=self.tmp_dir_)
        (_, state) = self.pass_.transform(tmp_path, state, None)

        variant = tmp_path.read_text()

        tmp_path.unlink()

        self.assertEqual(variant, 'int x = 0 / 2;\n')


class BalancedCurly3TestCase(unittest.TestCase):
    def setUp(self):
        self.tmp_dir_ = self.enterContext(tempfile.TemporaryDirectory())
        self.pass_ = BalancedPass('curly3')

    def test_no_match(self):
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as tmp_file:
            tmp_file.write('This is a simple test!\n')
            tmp_path = Path(tmp_file.name)

        state = self.pass_.new(tmp_path, tmp_dir=self.tmp_dir_)
        assert state is None

        tmp_path.unlink()

    def test_simple(self):
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as tmp_file:
            tmp_file.write('A a = { x, y };\n')
            tmp_path = Path(tmp_file.name)

        state = self.pass_.new(tmp_path, tmp_dir=self.tmp_dir_)
        (_, state) = self.pass_.transform(tmp_path, state, None)

        variant = tmp_path.read_text()

        tmp_path.unlink()

        self.assertEqual(variant, 'A a ;\n')

    def test_nested(self):
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as tmp_file:
            tmp_file.write('={  = {}};\n')
            tmp_path = Path(tmp_file.name)

        state = self.pass_.new(tmp_path, tmp_dir=self.tmp_dir_)
        all_transforms = collect_all_transforms(self.pass_, state, tmp_path)

        tmp_path.unlink()

        self.assertIn(b'={  };\n', all_transforms)
        self.assertIn(b';\n', all_transforms)

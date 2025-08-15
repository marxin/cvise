from pathlib import Path
import tempfile
import unittest

from cvise.passes.abstract import PassResult
from cvise.passes.balanced import BalancedPass
from cvise.tests.testabstract import collect_all_transforms


class BalancedParensTestCase(unittest.TestCase):
    def setUp(self):
        self.tmp_dir: Path = Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.input_path: Path = self.tmp_dir / 'test_case'
        self.pass_ = BalancedPass('parens')

    def test_parens_no_match(self):
        self.input_path.write_text('This is a simple test!\n')

        state = self.pass_.new(self.input_path, tmp_dir=self.tmp_dir)
        assert state is None

    def test_parens_simple(self):
        self.input_path.write_text('This is a (simple) test!\n')

        state = self.pass_.new(self.input_path, tmp_dir=self.tmp_dir)
        (_, state) = self.pass_.transform(
            self.input_path, state, process_event_notifier=None, original_test_case=self.input_path
        )

        variant = self.input_path.read_text()
        self.assertEqual(variant, 'This is a  test!\n')

    def test_parens_nested_outer(self):
        self.input_path.write_text('This (is a (simple) test)!\n')

        state = self.pass_.new(self.input_path, tmp_dir=self.tmp_dir)
        (_, state) = self.pass_.transform(
            self.input_path, state, process_event_notifier=None, original_test_case=self.input_path
        )

        variant = self.input_path.read_text()
        self.assertEqual(variant, 'This !\n')

    def test_parens_nested_inner(self):
        self.input_path.write_text('This (is a (simple) test)!\n')

        state = self.pass_.new(self.input_path, tmp_dir=self.tmp_dir)
        # Transform failed
        state = self.pass_.advance(self.input_path, state)
        (_, state) = self.pass_.transform(
            self.input_path, state, process_event_notifier=None, original_test_case=self.input_path
        )

        variant = self.input_path.read_text()
        self.assertEqual(variant, 'This (is a  test)!\n')


class BalancedParensOnlyTestCase(unittest.TestCase):
    def setUp(self):
        self.tmp_dir: Path = Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.input_path: Path = self.tmp_dir / 'test_case'
        self.pass_ = BalancedPass('parens-only')

    def test_parens_no_match(self):
        self.input_path.write_text('This is a simple test!\n')

        state = self.pass_.new(self.input_path, tmp_dir=self.tmp_dir)
        assert state is None

    def test_parens_simple(self):
        self.input_path.write_text('This is a (simple) test!\n')

        state = self.pass_.new(self.input_path, tmp_dir=self.tmp_dir)
        (_, state) = self.pass_.transform(
            self.input_path, state, process_event_notifier=None, original_test_case=self.input_path
        )

        variant = self.input_path.read_text()
        self.assertEqual(variant, 'This is a simple test!\n')

    def test_parens_nested_outer(self):
        self.input_path.write_text('This (is a (simple) test)!\n')

        state = self.pass_.new(self.input_path, tmp_dir=self.tmp_dir)
        all_transforms = collect_all_transforms(self.pass_, state, self.input_path)

        self.assertIn(b'This is a (simple) test!\n', all_transforms)
        self.assertIn(b'This is a (simple) test!\n', all_transforms)
        self.assertIn(b'This is a simple test!\n', all_transforms)

    def test_parens_nested_inner(self):
        self.input_path.write_text('This (is a (simple) test)!\n')

        state = self.pass_.new(self.input_path, tmp_dir=self.tmp_dir)
        # Transform failed
        state = self.pass_.advance(self.input_path, state)
        (_, state) = self.pass_.transform(
            self.input_path, state, process_event_notifier=None, original_test_case=self.input_path
        )

        variant = self.input_path.read_text()
        self.assertEqual(variant, 'This (is a simple test)!\n')

    def test_parens_nested_both(self):
        self.input_path.write_text('This (is a (simple) test)!\n')

        state = self.pass_.new(self.input_path, tmp_dir=self.tmp_dir)
        all_transforms = collect_all_transforms(self.pass_, state, self.input_path)

        self.assertIn(b'This (is a simple test)!\n', all_transforms)
        self.assertIn(b'This is a (simple) test!\n', all_transforms)
        self.assertIn(b'This is a simple test!\n', all_transforms)

    def test_parens_nested_all(self):
        self.input_path.write_text('(This) (is a (((more)) complex) test)!\n')

        state = self.pass_.new(self.input_path, tmp_dir=self.tmp_dir)
        (result, state) = self.pass_.transform(
            self.input_path, state, process_event_notifier=None, original_test_case=self.input_path
        )

        iteration = 0

        while result == PassResult.OK:
            state = self.pass_.advance_on_success(self.input_path, state)
            if state is None:
                break
            (result, state) = self.pass_.transform(
                self.input_path, state, process_event_notifier=None, original_test_case=self.input_path
            )
            iteration += 1

        variant = self.input_path.read_text()
        self.assertEqual(variant, 'This is a more complex test!\n')

    def test_parens_nested_no_success(self):
        self.input_path.write_text('(This) (is a (((more)) complex) test)!\n')

        state = self.pass_.new(self.input_path, tmp_dir=self.tmp_dir)
        all_transforms = collect_all_transforms(self.pass_, state, self.input_path)

        self.assertIn(b'This (is a (((more)) complex) test)!\n', all_transforms)
        self.assertIn(b'(This) (is a ((more) complex) test)!\n', all_transforms)
        self.assertIn(b'(This) (is a ((more)) complex test)!\n', all_transforms)
        self.assertIn(b'(This) is a (((more)) complex) test!\n', all_transforms)
        self.assertIn(b'This is a more complex test!\n', all_transforms)


class BalancedParensInsideTestCase(unittest.TestCase):
    def setUp(self):
        self.tmp_dir: Path = Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.input_path: Path = self.tmp_dir / 'test_case'
        self.pass_ = BalancedPass('parens-inside')

    def test_parens_no_match(self):
        self.input_path.write_text('This is a simple test!\n')

        state = self.pass_.new(self.input_path, tmp_dir=self.tmp_dir)
        assert state is None

    def test_parens_simple(self):
        self.input_path.write_text('This is a (simple) test!\n')

        state = self.pass_.new(self.input_path, tmp_dir=self.tmp_dir)
        (_, state) = self.pass_.transform(
            self.input_path, state, process_event_notifier=None, original_test_case=self.input_path
        )

        variant = self.input_path.read_text()
        self.assertEqual(variant, 'This is a () test!\n')

    def test_parens_nested_outer(self):
        self.input_path.write_text('This (is a (simple) test)!\n')

        state = self.pass_.new(self.input_path, tmp_dir=self.tmp_dir)
        (_, state) = self.pass_.transform(
            self.input_path, state, process_event_notifier=None, original_test_case=self.input_path
        )

        variant = self.input_path.read_text()
        self.assertEqual(variant, 'This ()!\n')

    def test_parens_nested_inner(self):
        self.input_path.write_text('This (is a (simple) test)!\n')

        state = self.pass_.new(self.input_path, tmp_dir=self.tmp_dir)
        # Transform failed
        state = self.pass_.advance(self.input_path, state)
        (_, state) = self.pass_.transform(
            self.input_path, state, process_event_notifier=None, original_test_case=self.input_path
        )

        variant = self.input_path.read_text()
        self.assertEqual(variant, 'This (is a () test)!\n')

    def test_parens_nested_both(self):
        self.input_path.write_text('This (is a (simple) test)!\n')

        state = self.pass_.new(self.input_path, tmp_dir=self.tmp_dir)
        all_transforms = collect_all_transforms(self.pass_, state, self.input_path)

        self.assertIn(b'This (is a () test)!\n', all_transforms)
        self.assertIn(b'This ()!\n', all_transforms)

    def test_parens_nested_all(self):
        self.input_path.write_text('(This) (is a (((more)) complex) test)!\n')

        state = self.pass_.new(self.input_path, tmp_dir=self.tmp_dir)
        all_transforms = collect_all_transforms(self.pass_, state, self.input_path)

        self.assertIn(b'() (is a (((more)) complex) test)!\n', all_transforms)
        self.assertIn(b'(This) (is a ((()) complex) test)!\n', all_transforms)
        self.assertIn(b'(This) (is a (() complex) test)!\n', all_transforms)
        self.assertIn(b'(This) (is a () test)!\n', all_transforms)
        self.assertIn(b'(This) ()!\n', all_transforms)
        self.assertIn(b'() ()!\n', all_transforms)

    def test_parens_nested_no_success(self):
        self.input_path.write_text('(This) (is a (((more)) complex) test)!\n')

        state = self.pass_.new(self.input_path, tmp_dir=self.tmp_dir)
        all_transforms = collect_all_transforms(self.pass_, state, self.input_path)

        self.assertIn(b'() (is a (((more)) complex) test)!\n', all_transforms)
        self.assertIn(b'(This) (is a ((()) complex) test)!\n', all_transforms)
        self.assertIn(b'(This) (is a (() complex) test)!\n', all_transforms)
        self.assertIn(b'(This) (is a () test)!\n', all_transforms)
        self.assertIn(b'(This) ()!\n', all_transforms)
        self.assertIn(b'() ()!\n', all_transforms)


class BalancedParensToZeroTestCase(unittest.TestCase):
    def setUp(self):
        self.tmp_dir: Path = Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.input_path: Path = self.tmp_dir / 'test_case'
        self.pass_ = BalancedPass('parens-to-zero')

    def test_no_match(self):
        self.input_path.write_text('This is a simple test!\n')

        state = self.pass_.new(self.input_path, tmp_dir=self.tmp_dir)
        assert state is None

    def test_simple(self):
        self.input_path.write_text('int x = (10 + y) / 2;\n')

        state = self.pass_.new(self.input_path, tmp_dir=self.tmp_dir)
        (_, state) = self.pass_.transform(
            self.input_path, state, process_event_notifier=None, original_test_case=self.input_path
        )

        variant = self.input_path.read_text()
        self.assertEqual(variant, 'int x = 0 / 2;\n')


class BalancedCurly3TestCase(unittest.TestCase):
    def setUp(self):
        self.tmp_dir: Path = Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.input_path: Path = self.tmp_dir / 'test_case'
        self.pass_ = BalancedPass('curly3')

    def test_no_match(self):
        self.input_path.write_text('This is a simple test!\n')

        state = self.pass_.new(self.input_path, tmp_dir=self.tmp_dir)
        assert state is None

    def test_simple(self):
        self.input_path.write_text('A a = { x, y };\n')

        state = self.pass_.new(self.input_path, tmp_dir=self.tmp_dir)
        (_, state) = self.pass_.transform(
            self.input_path, state, process_event_notifier=None, original_test_case=self.input_path
        )

        variant = self.input_path.read_text()
        self.assertEqual(variant, 'A a ;\n')

    def test_nested(self):
        self.input_path.write_text('={  = {}};\n')

        state = self.pass_.new(self.input_path, tmp_dir=self.tmp_dir)
        all_transforms = collect_all_transforms(self.pass_, state, self.input_path)

        self.assertIn(b'={  };\n', all_transforms)
        self.assertIn(b';\n', all_transforms)

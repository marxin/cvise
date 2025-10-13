from pathlib import Path
import tempfile
from typing import Any, Union
import unittest

from cvise.passes.abstract import PassResult
from cvise.passes.balanced import BalancedPass
from cvise.passes.hint_based import HintState
from cvise.tests.testabstract import collect_all_transforms, collect_all_transforms_dir
from cvise.utils.process import ProcessEventNotifier


class BalancedParensTestCase(unittest.TestCase):
    def setUp(self):
        # TODO: use enterContext() once Python 3.11 is the oldest supported release
        self.tmp_dir_obj = tempfile.TemporaryDirectory()
        self.tmp_dir: Path = Path(self.tmp_dir_obj.name)
        self.input_path: Path = self.tmp_dir / 'test_case'
        self.pass_ = BalancedPass('parens')

    def tearDown(self):
        self.tmp_dir_obj.cleanup()

    def _pass_new(self) -> Union[HintState, None]:
        return self.pass_.new(
            self.input_path, tmp_dir=self.tmp_dir, process_event_notifier=ProcessEventNotifier(None), dependee_hints=[]
        )

    def _transform(self, state: Any) -> tuple[PassResult, Any]:
        return self.pass_.transform(
            self.input_path, state, process_event_notifier=None, original_test_case=self.input_path, written_paths=set()
        )

    def test_parens_no_match(self):
        self.input_path.write_text('This is a simple test!\n')

        state = self._pass_new()
        assert state is None

    def test_parens_simple(self):
        self.input_path.write_text('This is a (simple) test!\n')

        state = self._pass_new()
        assert state is not None
        (_, state) = self._transform(state)

        variant = self.input_path.read_text()
        self.assertEqual(variant, 'This is a  test!\n')

    def test_parens_nested_outer(self):
        self.input_path.write_text('This (is a (simple) test)!\n')

        state = self._pass_new()
        assert state is not None
        (_, state) = self._transform(state)

        variant = self.input_path.read_text()
        self.assertEqual(variant, 'This !\n')

    def test_parens_nested_inner(self):
        self.input_path.write_text('This (is a (simple) test)!\n')

        state = self._pass_new()
        # Simulate that transforms failed until we get to the inner parenthesis.
        state = self.pass_.advance(self.input_path, state)
        state = self.pass_.advance(self.input_path, state)
        assert state is not None
        (_, state) = self._transform(state)

        variant = self.input_path.read_text()
        self.assertEqual(variant, 'This (is a  test)!\n')

    def test_parens_dir(self):
        self.input_path.mkdir()
        (self.input_path / 'a.txt').write_text('This is a (simple) test!\n')
        (self.input_path / 'b.txt').write_text('This (is a (simple) test)\n')

        state = self._pass_new()
        all_transforms = collect_all_transforms_dir(self.pass_, state, self.input_path)

        self.assertIn((('a.txt', b'This is a  test!\n'), ('b.txt', b'This \n')), all_transforms)


class BalancedParensOnlyTestCase(unittest.TestCase):
    def setUp(self):
        # TODO: use enterContext() once Python 3.11 is the oldest supported release
        self.tmp_dir_obj = tempfile.TemporaryDirectory()
        self.tmp_dir: Path = Path(self.tmp_dir_obj.name)
        self.input_path: Path = self.tmp_dir / 'test_case'
        self.pass_ = BalancedPass('parens-only')

    def tearDown(self):
        self.tmp_dir_obj.cleanup()

    def _pass_new(self) -> Union[HintState, None]:
        return self.pass_.new(
            self.input_path, tmp_dir=self.tmp_dir, process_event_notifier=ProcessEventNotifier(None), dependee_hints=[]
        )

    def _transform(self, state: Any) -> tuple[PassResult, Any]:
        return self.pass_.transform(
            self.input_path, state, process_event_notifier=None, original_test_case=self.input_path, written_paths=set()
        )

    def test_parens_no_match(self):
        self.input_path.write_text('This is a simple test!\n')

        state = self._pass_new()
        assert state is None

    def test_parens_simple(self):
        self.input_path.write_text('This is a (simple) test!\n')

        state = self._pass_new()
        assert state is not None
        (_, state) = self._transform(state)

        variant = self.input_path.read_text()
        self.assertEqual(variant, 'This is a simple test!\n')

    def test_parens_nested_outer(self):
        self.input_path.write_text('This (is a (simple) test)!\n')

        state = self._pass_new()
        all_transforms = collect_all_transforms(self.pass_, state, self.input_path)

        self.assertIn(b'This is a (simple) test!\n', all_transforms)
        self.assertIn(b'This is a (simple) test!\n', all_transforms)
        self.assertIn(b'This is a simple test!\n', all_transforms)

    def test_parens_nested_inner(self):
        self.input_path.write_text('This (is a (simple) test)!\n')

        state = self._pass_new()
        # Simulate that transforms failed until we get to the inner parenthesis.
        state = self.pass_.advance(self.input_path, state)
        state = self.pass_.advance(self.input_path, state)
        assert state is not None
        (_, state) = self._transform(state)

        variant = self.input_path.read_text()
        self.assertEqual(variant, 'This (is a simple test)!\n')

    def test_parens_nested_both(self):
        self.input_path.write_text('This (is a (simple) test)!\n')

        state = self._pass_new()
        all_transforms = collect_all_transforms(self.pass_, state, self.input_path)

        self.assertIn(b'This (is a simple test)!\n', all_transforms)
        self.assertIn(b'This is a (simple) test!\n', all_transforms)
        self.assertIn(b'This is a simple test!\n', all_transforms)

    def test_parens_nested_all(self):
        self.input_path.write_text('(This) (is a (((more)) complex) test)!\n')

        state = self._pass_new()
        assert state is not None
        (result, state) = self._transform(state)

        iteration = 0

        while result == PassResult.OK:
            state = self.pass_.advance_on_success(
                self.input_path,
                state,
                new_tmp_dir=self.tmp_dir,
                process_event_notifier=ProcessEventNotifier(None),
                dependee_hints=[],
            )
            if state is None:
                break
            (result, state) = self._transform(state)
            iteration += 1

        variant = self.input_path.read_text()
        self.assertEqual(variant, 'This is a more complex test!\n')

    def test_parens_nested_no_success(self):
        self.input_path.write_text('(This) (is a (((more)) complex) test)!\n')

        state = self._pass_new()
        all_transforms = collect_all_transforms(self.pass_, state, self.input_path)

        self.assertIn(b'This (is a (((more)) complex) test)!\n', all_transforms)
        self.assertIn(b'(This) (is a ((more) complex) test)!\n', all_transforms)
        self.assertIn(b'(This) (is a ((more)) complex test)!\n', all_transforms)
        self.assertIn(b'(This) is a (((more)) complex) test!\n', all_transforms)
        self.assertIn(b'This is a more complex test!\n', all_transforms)


class BalancedParensInsideTestCase(unittest.TestCase):
    def setUp(self):
        # TODO: use enterContext() once Python 3.11 is the oldest supported release
        self.tmp_dir_obj = tempfile.TemporaryDirectory()
        self.tmp_dir: Path = Path(self.tmp_dir_obj.name)
        self.input_path: Path = self.tmp_dir / 'test_case'
        self.pass_ = BalancedPass('parens-inside')

    def tearDown(self):
        self.tmp_dir_obj.cleanup()

    def _pass_new(self) -> Union[HintState, None]:
        return self.pass_.new(
            self.input_path, tmp_dir=self.tmp_dir, process_event_notifier=ProcessEventNotifier(None), dependee_hints=[]
        )

    def _transform(self, state: Any) -> tuple[PassResult, Any]:
        return self.pass_.transform(
            self.input_path, state, process_event_notifier=None, original_test_case=self.input_path, written_paths=set()
        )

    def test_parens_no_match(self):
        self.input_path.write_text('This is a simple test!\n')

        state = self._pass_new()
        assert state is None

    def test_parens_simple(self):
        self.input_path.write_text('This is a (simple) test!\n')

        state = self._pass_new()
        assert state is not None
        (_, state) = self._transform(state)

        variant = self.input_path.read_text()
        self.assertEqual(variant, 'This is a () test!\n')

    def test_parens_nested_outer(self):
        self.input_path.write_text('This (is a (simple) test)!\n')

        state = self._pass_new()
        assert state is not None
        (_, state) = self._transform(state)

        variant = self.input_path.read_text()
        self.assertEqual(variant, 'This ()!\n')

    def test_parens_nested_inner(self):
        self.input_path.write_text('This (is a (simple) test)!\n')

        state = self._pass_new()
        # Simulate that transforms failed until we get to the inner parenthesis.
        state = self.pass_.advance(self.input_path, state)
        state = self.pass_.advance(self.input_path, state)
        assert state is not None
        (_, state) = self._transform(state)

        variant = self.input_path.read_text()
        self.assertEqual(variant, 'This (is a () test)!\n')

    def test_parens_nested_both(self):
        self.input_path.write_text('This (is a (simple) test)!\n')

        state = self._pass_new()
        all_transforms = collect_all_transforms(self.pass_, state, self.input_path)

        self.assertIn(b'This (is a () test)!\n', all_transforms)
        self.assertIn(b'This ()!\n', all_transforms)

    def test_parens_nested_all(self):
        self.input_path.write_text('(This) (is a (((more)) complex) test)!\n')

        state = self._pass_new()
        all_transforms = collect_all_transforms(self.pass_, state, self.input_path)

        self.assertIn(b'() (is a (((more)) complex) test)!\n', all_transforms)
        self.assertIn(b'(This) (is a ((()) complex) test)!\n', all_transforms)
        self.assertIn(b'(This) (is a (() complex) test)!\n', all_transforms)
        self.assertIn(b'(This) (is a () test)!\n', all_transforms)
        self.assertIn(b'(This) ()!\n', all_transforms)
        self.assertIn(b'() ()!\n', all_transforms)

    def test_parens_nested_no_success(self):
        self.input_path.write_text('(This) (is a (((more)) complex) test)!\n')

        state = self._pass_new()
        all_transforms = collect_all_transforms(self.pass_, state, self.input_path)

        self.assertIn(b'() (is a (((more)) complex) test)!\n', all_transforms)
        self.assertIn(b'(This) (is a ((()) complex) test)!\n', all_transforms)
        self.assertIn(b'(This) (is a (() complex) test)!\n', all_transforms)
        self.assertIn(b'(This) (is a () test)!\n', all_transforms)
        self.assertIn(b'(This) ()!\n', all_transforms)
        self.assertIn(b'() ()!\n', all_transforms)


class BalancedParensToZeroTestCase(unittest.TestCase):
    def setUp(self):
        # TODO: use enterContext() once Python 3.11 is the oldest supported release
        self.tmp_dir_obj = tempfile.TemporaryDirectory()
        self.tmp_dir: Path = Path(self.tmp_dir_obj.name)
        self.input_path: Path = self.tmp_dir / 'test_case'
        self.pass_ = BalancedPass('parens-to-zero')

    def tearDown(self):
        self.tmp_dir_obj.cleanup()

    def _pass_new(self) -> Union[HintState, None]:
        return self.pass_.new(
            self.input_path, tmp_dir=self.tmp_dir, process_event_notifier=ProcessEventNotifier(None), dependee_hints=[]
        )

    def _transform(self, state: Any) -> tuple[PassResult, Any]:
        return self.pass_.transform(
            self.input_path, state, process_event_notifier=None, original_test_case=self.input_path, written_paths=set()
        )

    def test_no_match(self):
        self.input_path.write_text('This is a simple test!\n')

        state = self._pass_new()
        assert state is None

    def test_simple(self):
        self.input_path.write_text('int x = (10 + y) / 2;\n')

        state = self._pass_new()
        assert state is not None
        (_, state) = self._transform(state)

        variant = self.input_path.read_text()
        self.assertEqual(variant, 'int x = 0 / 2;\n')


class BalancedCurly3TestCase(unittest.TestCase):
    def setUp(self):
        # TODO: use enterContext() once Python 3.11 is the oldest supported release
        self.tmp_dir_obj = tempfile.TemporaryDirectory()
        self.tmp_dir: Path = Path(self.tmp_dir_obj.name)
        self.input_path: Path = self.tmp_dir / 'test_case'
        self.pass_ = BalancedPass('curly3')

    def tearDown(self):
        self.tmp_dir_obj.cleanup()

    def _pass_new(self) -> Union[HintState, None]:
        return self.pass_.new(
            self.input_path, tmp_dir=self.tmp_dir, process_event_notifier=ProcessEventNotifier(None), dependee_hints=[]
        )

    def _transform(self, state: Any) -> tuple[PassResult, Any]:
        return self.pass_.transform(
            self.input_path, state, process_event_notifier=None, original_test_case=self.input_path, written_paths=set()
        )

    def test_no_match(self):
        self.input_path.write_text('This is a simple test!\n')

        state = self._pass_new()
        assert state is None

    def test_simple(self):
        self.input_path.write_text('A a = { x, y };\n')

        state = self._pass_new()
        assert state is not None
        (_, state) = self._transform(state)

        variant = self.input_path.read_text()
        self.assertEqual(variant, 'A a ;\n')

    def test_nested(self):
        self.input_path.write_text('={  = {}};\n')

        state = self._pass_new()
        all_transforms = collect_all_transforms(self.pass_, state, self.input_path)

        self.assertIn(b'={  };\n', all_transforms)
        self.assertIn(b';\n', all_transforms)

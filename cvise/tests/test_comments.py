from pathlib import Path
import tempfile
from typing import Union
import unittest

from cvise.passes.abstract import PassResult
from cvise.passes.comments import CommentsPass
from cvise.passes.hint_based import HintState
from cvise.tests.testabstract import validate_stored_hints
from cvise.utils.process import ProcessEventNotifier


class CommentsTestCase(unittest.TestCase):
    def setUp(self):
        # TODO: use enterContext() once Python 3.11 is the oldest supported release
        self.tmp_dir_obj = tempfile.TemporaryDirectory()
        self.tmp_dir: Path = Path(self.tmp_dir_obj.name)
        self.input_path: Path = self.tmp_dir / 'test_case'
        self.pass_ = CommentsPass()

    def tearDown(self):
        self.tmp_dir_obj.cleanup()

    def _pass_new(self) -> Union[HintState, None]:
        return self.pass_.new(
            self.input_path, tmp_dir=self.tmp_dir, process_event_notifier=ProcessEventNotifier(None), dependee_hints=[]
        )

    def test_block(self):
        self.input_path.write_text('This /* contains *** /* two */ /*comments*/!\n')

        state = self._pass_new()
        assert state is not None
        validate_stored_hints(state, self.pass_, self.input_path)
        (_, state) = self.pass_.transform(
            self.input_path,
            state,
            process_event_notifier=ProcessEventNotifier(None),
            original_test_case=self.input_path,
        )

        variant = self.input_path.read_text()
        self.assertEqual(variant, 'This  !\n')

    def test_line(self):
        self.input_path.write_text('This ///contains //two\n //comments\n!\n')

        state = self._pass_new()
        assert state is not None
        validate_stored_hints(state, self.pass_, self.input_path)
        (_, state) = self.pass_.transform(
            self.input_path,
            state,
            process_event_notifier=ProcessEventNotifier(None),
            original_test_case=self.input_path,
        )

        variant = self.input_path.read_text()
        self.assertEqual(variant, 'This \n \n!\n')

    def test_success(self):
        self.input_path.write_text('/*This*/ ///contains //two\n //comments\n!\n')

        state = self._pass_new()
        assert state is not None
        validate_stored_hints(state, self.pass_, self.input_path)
        (result, state) = self.pass_.transform(
            self.input_path,
            state,
            process_event_notifier=ProcessEventNotifier(None),
            original_test_case=self.input_path,
        )

        while result == PassResult.OK and state is not None:
            state = self.pass_.advance_on_success(
                self.input_path,
                state,
                new_tmp_dir=self.tmp_dir,
                process_event_notifier=ProcessEventNotifier(None),
                dependee_hints=[],
            )
            if state is None:
                break
            (result, state) = self.pass_.transform(
                self.input_path,
                state,
                process_event_notifier=ProcessEventNotifier(None),
                original_test_case=self.input_path,
            )

        variant = self.input_path.read_text()
        self.assertEqual(variant, ' \n \n!\n')

    def test_no_success(self):
        self.input_path.write_text('/*This*/ ///contains //two\n //comments\n!\n')

        state = self._pass_new()
        assert state is not None
        validate_stored_hints(state, self.pass_, self.input_path)
        (result, state) = self.pass_.transform(
            self.input_path,
            state,
            process_event_notifier=ProcessEventNotifier(None),
            original_test_case=self.input_path,
        )

        while result == PassResult.OK and state is not None:
            self.input_path.write_text('/*This*/ ///contains //two\n //comments\n!\n')

            state = self.pass_.advance(self.input_path, state)
            if state is None:
                break
            (result, state) = self.pass_.transform(
                self.input_path,
                state,
                process_event_notifier=ProcessEventNotifier(None),
                original_test_case=self.input_path,
            )

    def test_non_ascii(self):
        self.input_path.write_bytes(b'int x;\n// Streichholzsch\xc3\xa4chtelchen\nchar t[] = "nonutf\xff";\n// \xff\n')

        state = self._pass_new()
        assert state is not None
        validate_stored_hints(state, self.pass_, self.input_path)
        (_, state) = self.pass_.transform(
            self.input_path,
            state,
            process_event_notifier=ProcessEventNotifier(None),
            original_test_case=self.input_path,
        )

        variant = self.input_path.read_bytes()
        self.assertEqual(variant, b'int x;\n\nchar t[] = "nonutf\xff";\n\n')

    def test_multi_file(self):
        self.input_path.mkdir()
        (self.input_path / 'foo.h').write_text('// Foo\nint foo;\n')
        (self.input_path / 'bar.cc').write_text('int\n// bar!\nbar;\n')

        state = self._pass_new()
        assert state is not None
        output_path = self.tmp_dir / 'transformed_test_case'
        validate_stored_hints(state, self.pass_, self.input_path)
        (_, state) = self.pass_.transform(
            output_path, state, process_event_notifier=ProcessEventNotifier(None), original_test_case=self.input_path
        )

        self.assertEqual((output_path / 'foo.h').read_text(), '\nint foo;\n')
        self.assertEqual((output_path / 'bar.cc').read_text(), 'int\n\nbar;\n')

from pathlib import Path
import tempfile
import unittest

from cvise.passes.abstract import PassResult
from cvise.passes.comments import CommentsPass
from cvise.tests.testabstract import validate_stored_hints


class CommentsTestCase(unittest.TestCase):
    def setUp(self):
        self.tmp_dir: Path = Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.input_path: Path = self.tmp_dir / 'test_case'
        self.pass_ = CommentsPass()

    def test_block(self):
        self.input_path.write_text('This /* contains *** /* two */ /*comments*/!\n')

        state = self.pass_.new(self.input_path, tmp_dir=self.tmp_dir)
        validate_stored_hints(state)
        (_, state) = self.pass_.transform(
            self.input_path, state, process_event_notifier=None, original_test_case=self.input_path
        )

        variant = self.input_path.read_text()
        self.assertEqual(variant, 'This  !\n')

    def test_line(self):
        self.input_path.write_text('This ///contains //two\n //comments\n!\n')

        state = self.pass_.new(self.input_path, tmp_dir=self.tmp_dir)
        validate_stored_hints(state)
        (_, state) = self.pass_.transform(
            self.input_path, state, process_event_notifier=None, original_test_case=self.input_path
        )

        variant = self.input_path.read_text()
        self.assertEqual(variant, 'This \n \n!\n')

    def test_success(self):
        self.input_path.write_text('/*This*/ ///contains //two\n //comments\n!\n')

        state = self.pass_.new(self.input_path, tmp_dir=self.tmp_dir)
        validate_stored_hints(state)
        (result, state) = self.pass_.transform(
            self.input_path, state, process_event_notifier=None, original_test_case=self.input_path
        )

        while result == PassResult.OK and state is not None:
            state = self.pass_.advance_on_success(self.input_path, state)
            if state is None:
                break
            (result, state) = self.pass_.transform(
                self.input_path, state, process_event_notifier=None, original_test_case=self.input_path
            )

        variant = self.input_path.read_text()
        self.assertEqual(variant, ' \n \n!\n')

    def test_no_success(self):
        self.input_path.write_text('/*This*/ ///contains //two\n //comments\n!\n')

        state = self.pass_.new(self.input_path, tmp_dir=self.tmp_dir)
        validate_stored_hints(state)
        (result, state) = self.pass_.transform(
            self.input_path, state, process_event_notifier=None, original_test_case=self.input_path
        )

        while result == PassResult.OK and state is not None:
            self.input_path.write_text('/*This*/ ///contains //two\n //comments\n!\n')

            state = self.pass_.advance(self.input_path, state)
            if state is None:
                break
            (result, state) = self.pass_.transform(
                self.input_path, state, process_event_notifier=None, original_test_case=self.input_path
            )

    def test_non_ascii(self):
        self.input_path.write_bytes(b'int x;\n// Streichholzsch\xc3\xa4chtelchen\nchar t[] = "nonutf\xff";\n// \xff\n')

        state = self.pass_.new(self.input_path, tmp_dir=self.tmp_dir)
        validate_stored_hints(state)
        (_, state) = self.pass_.transform(
            self.input_path, state, process_event_notifier=None, original_test_case=self.input_path
        )

        variant = self.input_path.read_bytes()
        self.assertEqual(variant, b'int x;\n\nchar t[] = "nonutf\xff";\n\n')

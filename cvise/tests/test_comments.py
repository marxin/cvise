from pathlib import Path
import tempfile
import unittest

from cvise.passes.abstract import PassResult
from cvise.passes.comments import CommentsPass
from cvise.tests.testabstract import validate_stored_hints


class CommentsTestCase(unittest.TestCase):
    def setUp(self):
        self.tmp_dir_ = self.enterContext(tempfile.TemporaryDirectory())
        self.pass_ = CommentsPass()

    def test_block(self):
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as tmp_file:
            tmp_file.write('This /* contains *** /* two */ /*comments*/!\n')
            tmp_path = Path(tmp_file.name)

        state = self.pass_.new(tmp_path, tmp_dir=self.tmp_dir_)
        validate_stored_hints(state)
        (_, state) = self.pass_.transform(tmp_path, state, None)

        variant = tmp_path.read_text()

        tmp_path.unlink()

        self.assertEqual(variant, 'This  !\n')

    def test_line(self):
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as tmp_file:
            tmp_file.write('This ///contains //two\n //comments\n!\n')
            tmp_path = Path(tmp_file.name)

        state = self.pass_.new(tmp_path, tmp_dir=self.tmp_dir_)
        validate_stored_hints(state)
        (_, state) = self.pass_.transform(tmp_path, state, None)

        variant = tmp_path.read_text()

        tmp_path.unlink()

        self.assertEqual(variant, 'This \n \n!\n')

    def test_success(self):
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as tmp_file:
            tmp_file.write('/*This*/ ///contains //two\n //comments\n!\n')
            tmp_path = Path(tmp_file.name)

        state = self.pass_.new(tmp_path, tmp_dir=self.tmp_dir_)
        validate_stored_hints(state)
        (result, state) = self.pass_.transform(tmp_path, state, None)

        while result == PassResult.OK and state is not None:
            state = self.pass_.advance_on_success(tmp_path, state)
            if state is None:
                break
            (result, state) = self.pass_.transform(tmp_path, state, None)

        variant = tmp_path.read_text()

        tmp_path.unlink()

        self.assertEqual(variant, ' \n \n!\n')

    def test_no_success(self):
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as tmp_file:
            tmp_file.write('/*This*/ ///contains //two\n //comments\n!\n')
            tmp_path = Path(tmp_file.name)

        state = self.pass_.new(tmp_path, tmp_dir=self.tmp_dir_)
        validate_stored_hints(state)
        (result, state) = self.pass_.transform(tmp_path, state, None)

        while result == PassResult.OK and state is not None:
            tmp_path.write_text('/*This*/ ///contains //two\n //comments\n!\n')

            state = self.pass_.advance(tmp_path, state)
            if state is None:
                break
            (result, state) = self.pass_.transform(tmp_path, state, None)

        tmp_path.unlink()

    def test_non_ascii(self):
        with tempfile.NamedTemporaryFile(mode='wb', delete=False) as tmp_file:
            tmp_file.write(b'int x;\n// Streichholzsch\xc3\xa4chtelchen\nchar t[] = "nonutf\xff";\n// \xff\n')
            tmp_path = Path(tmp_file.name)

        state = self.pass_.new(tmp_path, tmp_dir=self.tmp_dir_)
        validate_stored_hints(state)
        (_, state) = self.pass_.transform(tmp_path, state, None)

        variant = tmp_path.read_bytes()

        tmp_path.unlink()

        self.assertEqual(variant, b'int x;\n\nchar t[] = "nonutf\xff";\n\n')

import os
import tempfile
import unittest

from cvise.passes.abstract import PassResult
from cvise.passes.comments import CommentsPass


class CommentsTestCase(unittest.TestCase):
    def setUp(self):
        self.tmp_dir_ = self.enterContext(tempfile.TemporaryDirectory())
        self.pass_ = CommentsPass()

    def test_block(self):
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as tmp_file:
            tmp_file.write('This /* contains *** /* two */ /*comments*/!\n')

        state = self.pass_.new(tmp_file.name, tmp_dir=self.tmp_dir_)
        (_, state) = self.pass_.transform(tmp_file.name, state, None)

        with open(tmp_file.name) as variant_file:
            variant = variant_file.read()

        os.unlink(tmp_file.name)

        self.assertEqual(variant, 'This  !\n')

    def test_line(self):
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as tmp_file:
            tmp_file.write('This ///contains //two\n //comments\n!\n')

        state = self.pass_.new(tmp_file.name, tmp_dir=self.tmp_dir_)
        (_, state) = self.pass_.transform(tmp_file.name, state, None)

        with open(tmp_file.name) as variant_file:
            variant = variant_file.read()

        os.unlink(tmp_file.name)

        self.assertEqual(variant, 'This \n \n!\n')

    def test_success(self):
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as tmp_file:
            tmp_file.write('/*This*/ ///contains //two\n //comments\n!\n')

        state = self.pass_.new(tmp_file.name, tmp_dir=self.tmp_dir_)
        (result, state) = self.pass_.transform(tmp_file.name, state, None)

        while result == PassResult.OK and state is not None:
            state = self.pass_.advance_on_success(tmp_file.name, state)
            if state is None:
                break
            (result, state) = self.pass_.transform(tmp_file.name, state, None)

        with open(tmp_file.name) as variant_file:
            variant = variant_file.read()

        os.unlink(tmp_file.name)

        self.assertEqual(variant, ' \n \n!\n')

    def test_no_success(self):
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as tmp_file:
            tmp_file.write('/*This*/ ///contains //two\n //comments\n!\n')

        state = self.pass_.new(tmp_file.name, tmp_dir=self.tmp_dir_)
        (result, state) = self.pass_.transform(tmp_file.name, state, None)

        while result == PassResult.OK and state is not None:
            with tempfile.NamedTemporaryFile(mode='w', delete=False) as tmp_file:
                tmp_file.write('/*This*/ ///contains //two\n //comments\n!\n')

            state = self.pass_.advance(tmp_file.name, state)
            if state is None:
                break
            (result, state) = self.pass_.transform(tmp_file.name, state, None)

        os.unlink(tmp_file.name)

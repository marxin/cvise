import os
import pytest
import tempfile
import unittest

from cvise.passes.line_markers import LineMarkersPass


@pytest.fixture
def input_path(tmp_path):
    return tmp_path / 'input.cc'


def init_pass(input_path):
    pass_ = LineMarkersPass()
    state = pass_.new(input_path)
    return pass_, state


def test_all(input_path):
    input_path.write_text("# 1 'foo.h'\n# 2 'bar.h'\n#4   'x.h'")
    pass_, state = init_pass(input_path)

    (_, state) = pass_.transform(input_path, state, None)

    assert state.index == 0
    assert state.instances == 3
    assert input_path.read_text() == ''


def test_only_last(input_path):
    input_path.write_text("# 1 'foo.h'\n# 2 'bar.h'\n#4   'x.h\nint x = 2;")
    pass_, state = init_pass(input_path)

    (_, state) = pass_.transform(input_path, state, None)

    assert input_path.read_text() == 'int x = 2;'

"""Tests ClangHintsPass.

Note that these tests are focused on the Python side of this pass. The clang_delta counterpart has its own comprehensive
tests in clang_delta/tests/test_clang_delta.py."""

from pathlib import Path
import subprocess

from cvise.passes.clanghints import ClangHintsPass
from cvise.tests.testabstract import collect_all_transforms, validate_stored_hints
from cvise.utils.externalprograms import find_external_programs


def get_data_path(testcase):
    return Path(__file__).parent.parent.parent / 'clang_delta' / 'tests' / testcase


def init_pass(transformation, tmp_dir, input_path):
    pass_ = ClangHintsPass(transformation, find_external_programs())
    pass_.user_clang_delta_std = None
    state = pass_.new(input_path, tmp_dir=tmp_dir)
    validate_stored_hints(state)
    return pass_, state


def test_class(tmp_path):
    input_path = get_data_path('remove-unused-function/class.cc')
    p, state = init_pass('remove-unused-function', tmp_path, input_path)
    all_transforms = collect_all_transforms(p, state, input_path)

    expected_path = get_data_path('remove-unused-function/class.output')
    assert expected_path.read_text() in all_transforms


def test_const(tmp_path):
    input_path = get_data_path('remove-unused-function/const.cc')
    p, state = init_pass('remove-unused-function', tmp_path, input_path)
    all_transforms = collect_all_transforms(p, state, input_path)

    assert get_data_path('remove-unused-function/const.output').read_text() in all_transforms
    assert get_data_path('remove-unused-function/const.output2').read_text() in all_transforms


def test_inline_ns(tmp_path):
    input_path = get_data_path('remove-unused-function/inline_ns.cc')
    p, state = init_pass('remove-unused-function', tmp_path, input_path)

    assert state is None


def test_malformed_code(tmp_path):
    input_path = tmp_path / 'input.cc'
    input_path.write_text('!?badbadbad@#')
    p, state = init_pass('remove-unused-function', tmp_path, input_path)

    assert state is None


def test_clang_delta_crash(tmp_path, monkeypatch):
    """Test the case of clang_delta crashing.

    We simulate this by patching the subprocess API to return a nonzero exit code and an empty output."""

    class StubPopen:
        def __init__(self, *args, **kwargs):
            self.stdout = iter([])
            self.returncode = 1

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

    input_path = tmp_path / 'input.c'
    input_path.touch()
    monkeypatch.setattr(subprocess, 'Popen', StubPopen)
    p, state = init_pass('remove-unused-function', tmp_path, input_path)

    assert state is None

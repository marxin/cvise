"""Tests ClangHintsPass.

Note that these tests are focused on the Python side of this pass. The clang_delta counterpart has its own comprehensive
tests in clang_delta/tests/test_clang_delta.py."""

from pathlib import Path
import subprocess
from typing import Any, Tuple

from cvise.passes.clanghints import ClangHintsPass
from cvise.tests.testabstract import collect_all_transforms, validate_stored_hints
from cvise.utils.externalprograms import find_external_programs
from cvise.utils.process import ProcessEventNotifier


def get_data_path(testcase: str) -> Path:
    return Path(__file__).parent.parent.parent / 'clang_delta' / 'tests' / testcase


def init_pass(transformation: str, tmp_dir: Path, input_path: Path) -> Tuple[ClangHintsPass, Any]:
    pass_ = ClangHintsPass(transformation, find_external_programs())
    pass_.user_clang_delta_std = None
    state = pass_.new(
        input_path,
        tmp_dir=tmp_dir,
        job_timeout=100,
        process_event_notifier=ProcessEventNotifier(None),
        dependee_hints=[],
    )
    validate_stored_hints(state, pass_, input_path)
    return pass_, state


def test_class(tmp_path: Path):
    input_path = get_data_path('remove-unused-function/class.cc')
    p, state = init_pass('remove-unused-function', tmp_path, input_path)
    all_transforms = collect_all_transforms(p, state, input_path)

    expected_path = get_data_path('remove-unused-function/class.output')
    assert expected_path.read_bytes() in all_transforms


def test_const(tmp_path: Path):
    input_path = get_data_path('remove-unused-function/const.cc')
    p, state = init_pass('remove-unused-function', tmp_path, input_path)
    all_transforms = collect_all_transforms(p, state, input_path)

    assert get_data_path('remove-unused-function/const.output').read_bytes() in all_transforms
    assert get_data_path('remove-unused-function/const.output2').read_bytes() in all_transforms


def test_inline_ns(tmp_path: Path):
    input_path = get_data_path('remove-unused-function/inline_ns.cc')
    p, state = init_pass('remove-unused-function', tmp_path, input_path)

    assert state is None


def test_malformed_code(tmp_path: Path):
    input_path = tmp_path / 'input.cc'
    input_path.write_text('!?badbadbad@#')
    p, state = init_pass('remove-unused-function', tmp_path, input_path)

    assert state is None


def test_clang_delta_crash(tmp_path: Path, monkeypatch):
    """Test the case of clang_delta crashing.

    We simulate this by patching the subprocess API to return a nonzero exit code and an empty output."""

    def stub_run(arg, **kwargs):
        return subprocess.CompletedProcess(arg, returncode=1, stdout='', stderr='')

    input_path = tmp_path / 'input.c'
    input_path.touch()
    monkeypatch.setattr(subprocess, 'run', stub_run)
    p, state = init_pass('remove-unused-function', tmp_path, input_path)

    assert state is None


def test_clang_delta_timeout(tmp_path: Path, monkeypatch):
    """Test the case of clang_delta timing out.

    We simulate this by patching the subprocess API to raise a timeout error."""

    def stub_run(args, **kwargs):
        raise subprocess.TimeoutExpired(args, timeout=0)

    input_path = tmp_path / 'input.c'
    input_path.touch()
    monkeypatch.setattr(subprocess, 'run', stub_run)
    p, state = init_pass('remove-unused-function', tmp_path, input_path)

    assert state is None

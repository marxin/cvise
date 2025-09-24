from pathlib import Path
import pytest
from typing import Any, Tuple

from cvise.passes.clangincludegraph import ClangIncludeGraphPass
from cvise.tests.testabstract import validate_stored_hints
from cvise.utils.externalprograms import find_external_programs
from cvise.utils.hint import load_hints
from cvise.utils.process import ProcessEventNotifier


def init_pass(tmp_dir: Path, input_path: Path) -> Tuple[ClangIncludeGraphPass, Any]:
    pass_ = ClangIncludeGraphPass(external_programs=find_external_programs())
    state = pass_.new(input_path, tmp_dir=tmp_dir, process_event_notifier=ProcessEventNotifier(None), dependee_hints=[])
    validate_stored_hints(state, pass_, input_path)
    return pass_, state


def test_header_chain(tmp_path: Path):
    input_dir = tmp_path / 'test_case'
    input_dir.mkdir()
    (input_dir / 'main.cc').write_text('#include "foo.h"\n')
    (input_dir / 'foo.h').write_text('#include "bar.h"')
    (input_dir / 'bar.h').touch()
    (input_dir / 'Makefile').write_text('a.out:\n\tgcc main.cc\n')
    p, state = init_pass(tmp_path, input_dir)
    assert state is not None
    bundle_paths = state.hint_bundle_paths()

    assert b'@fileref' in bundle_paths
    bundle = load_hints(bundle_paths[b'@fileref'], None, None)
    refs = {bundle.vocabulary[h.extra] for h in bundle.hints}
    assert refs == {b'bar.h', b'foo.h'}


@pytest.mark.parametrize('cmd_flag', ['-Isub', '-I sub', '-iquotesub', '-iquote sub'])
def test_include_search_path(tmp_path: Path, cmd_flag: str):
    input_dir = tmp_path / 'test_case'
    input_dir.mkdir()
    sub_dir = input_dir / 'sub'
    sub_dir.mkdir()
    (input_dir / 'main.cc').write_text('#include "foo.h"\n')
    (input_dir / sub_dir / 'foo.h').touch()
    (input_dir / 'Makefile').write_text(f'a.out:\n\tgcc -c {cmd_flag} -Wall main.cc\n')
    p, state = init_pass(tmp_path, input_dir)
    assert state is not None
    bundle_paths = state.hint_bundle_paths()

    assert b'@fileref' in bundle_paths
    bundle = load_hints(bundle_paths[b'@fileref'], None, None)
    refs = {bundle.vocabulary[h.extra] for h in bundle.hints}
    assert refs == {b'sub/foo.h'}

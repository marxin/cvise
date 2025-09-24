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
    (input_dir / 'Makefile').write_text(
        """
a.out:
\tgcc main.cc
        """
    )
    p, state = init_pass(tmp_path, input_dir)
    assert state is not None
    bundle_paths = state.hint_bundle_paths()

    assert b'@fileref' in bundle_paths
    bundle = load_hints(bundle_paths[b'@fileref'], None, None)
    refs = {bundle.vocabulary[h.extra] for h in bundle.hints}
    assert refs == {b'bar.h', b'foo.h'}


def test_multiple_commands(tmp_path: Path):
    input_dir = tmp_path / 'test_case'
    input_dir.mkdir()
    (input_dir / 'foo.c').write_text('#include "foo.h"\n')
    (input_dir / 'foo.h').write_text('#include "common.h"\n')
    (input_dir / 'bar.c').write_text('#include "bar.h"\n')
    (input_dir / 'bar.h').write_text('#include "common.h"\n')
    (input_dir / 'common.h').touch()
    (input_dir / 'Makefile').write_text(
        """
foo.o:
\tgcc foo.c -o foo.o
bar.o:
\tgcc -c bar.c
program:
\tgcc -o program foo.o bar.o
        """
    )
    p, state = init_pass(tmp_path, input_dir)
    assert state is not None
    bundle_paths = state.hint_bundle_paths()

    assert b'@fileref' in bundle_paths
    bundle = load_hints(bundle_paths[b'@fileref'], None, None)
    refs = {bundle.vocabulary[h.extra] for h in bundle.hints}
    assert refs == {b'bar.h', b'common.h', b'foo.h'}


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


def test_unrelated_commands(tmp_path: Path):
    """Test that we don't run preprocessor on files only mentioned in non-compilation commands."""
    input_dir = tmp_path / 'test_case'
    input_dir.mkdir()
    sub_dir = input_dir / 'sub'
    sub_dir.mkdir()
    (input_dir / 'good.cpp').write_text('#include "header.hpp"\n')
    (input_dir / 'header.hpp').touch()
    (input_dir / 'bad.cpp').write_text('#include "nonexisting.h"\n')
    (input_dir / 'Makefile').write_text(
        """
a.out:
\tgcc good.cpp
foo.txt:
\tcat bad.cpp > foo.txt
        """
    )
    p, state = init_pass(tmp_path, input_dir)
    assert state is not None
    bundle_paths = state.hint_bundle_paths()

    assert b'@fileref' in bundle_paths
    bundle = load_hints(bundle_paths[b'@fileref'], None, None)
    refs = {bundle.vocabulary[h.extra] for h in bundle.hints}
    assert refs == {b'header.hpp'}


def test_some_commands_fail(tmp_path: Path):
    """Test that preprocessor failures on some of the files don't prevent us from reporting hints on others."""
    input_dir = tmp_path / 'test_case'
    input_dir.mkdir()
    (input_dir / 'good1.c').write_text('#include "good1.h"\n')
    (input_dir / 'good1.h').touch()
    (input_dir / 'bad.c').write_text('#include "nonexisting.h"\n')
    (input_dir / 'good2.c').write_text('#include "good2.h"\n')
    (input_dir / 'good2.h').touch()
    (input_dir / 'Makefile').write_text(
        """
good1.o:
\tgcc -c good1.c
bad.o:
\tgcc -c bad.c
good2.o:
\tgcc -c good2.c
        """
    )
    p, state = init_pass(tmp_path, input_dir)
    assert state is not None
    bundle_paths = state.hint_bundle_paths()

    assert b'@fileref' in bundle_paths
    bundle = load_hints(bundle_paths[b'@fileref'], None, None)
    refs = {bundle.vocabulary[h.extra] for h in bundle.hints}
    assert refs == {b'good1.h', b'good2.h'}

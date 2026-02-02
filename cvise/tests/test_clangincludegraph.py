from pathlib import Path
from typing import Any

import pytest

from cvise.passes.clangincludegraph import ClangIncludeGraphPass
from cvise.passes.hint_based import HintBasedPass
from cvise.tests.testabstract import load_ref_hints, validate_stored_hints
from cvise.utils.externalprograms import find_external_programs
from cvise.utils.hint import Hint, HintBundle, load_hints
from cvise.utils.process import ProcessEventNotifier


def init_pass(tmp_dir: Path, input_path: Path) -> tuple[ClangIncludeGraphPass, Any]:
    pass_ = ClangIncludeGraphPass(external_programs=find_external_programs())

    # 1. Simulate the MakefilePass outputs.
    mk_bundle = HintBundle(vocabulary=[b'@makefile'], hints=[])
    for mk_path in input_path.rglob('**/Makefile'):
        mk_bundle.vocabulary.append(str(mk_path.relative_to(input_path)).encode())
        path_id = len(mk_bundle.vocabulary) - 1
        mk_bundle.hints.append(Hint(type=0, extra=path_id))

    # 2. Execute the subordinate passes.
    sub_passes = pass_.create_subordinate_passes()
    sub_bundles = []
    for p in sub_passes:
        assert isinstance(p, HintBasedPass)
        assert set(p.output_hint_types()) <= set(pass_.input_hint_types())
        sub_state = p.new(
            input_path, tmp_dir=tmp_dir, process_event_notifier=ProcessEventNotifier(None), dependee_hints=[mk_bundle]
        )
        validate_stored_hints(sub_state, p, input_path)
        if sub_state is None:
            continue
        for path in sub_state.hint_bundle_paths().values():
            sub_bundles.append(load_hints(path, begin_index=None, end_index=None))

    # 3. Initialize the main pass.
    state = pass_.new(
        input_path, tmp_dir=tmp_dir, process_event_notifier=ProcessEventNotifier(None), dependee_hints=sub_bundles
    )
    validate_stored_hints(state, pass_, input_path)
    return pass_, state


def test_header_chain(tmp_path: Path):
    input_dir = tmp_path / 'test_case'
    input_dir.mkdir()
    (input_dir / 'main.cc').write_text('#include "foo.h"\n')
    (input_dir / 'foo.h').write_text('// hello\n#include "bar.h"')
    (input_dir / 'bar.h').touch()
    (input_dir / 'makefile').write_text(
        """
a.out:
\tgcc main.cc
        """
    )
    p, state = init_pass(tmp_path, input_dir)
    assert state is not None

    assert load_ref_hints(state, b'@fileref') == {(b'main.cc', 0, 16, b'foo.h'), (b'foo.h', 9, 24, b'bar.h')}


def test_multiple_commands(tmp_path: Path):
    input_dir = tmp_path / 'test_case'
    input_dir.mkdir()
    (input_dir / 'foo.c').write_text('#include "foo.h"\n')
    (input_dir / 'foo.h').write_text('#include "common.h"\n')
    (input_dir / 'bar.c').write_text('#include "bar.h"\n')
    (input_dir / 'bar.h').write_text('#include "common.h"\n')
    (input_dir / 'common.h').touch()
    (input_dir / 'makefile').write_text(
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

    assert load_ref_hints(state, b'@fileref') == {
        (b'foo.c', 0, 16, b'foo.h'),
        (b'foo.h', 0, 19, b'common.h'),
        (b'bar.c', 0, 16, b'bar.h'),
        (b'bar.h', 0, 19, b'common.h'),
    }


@pytest.mark.parametrize('cmd_flag', ['-Isub', '-I sub', '-iquotesub', '-iquote sub'])
def test_include_search_path(tmp_path: Path, cmd_flag: str):
    input_dir = tmp_path / 'test_case'
    input_dir.mkdir()
    sub_dir = input_dir / 'sub'
    sub_dir.mkdir()
    (input_dir / 'main.cc').write_text('#include "foo.h"\n')
    (input_dir / sub_dir / 'foo.h').touch()
    (input_dir / 'makefile').write_text(f'a.out:\n\tgcc -c {cmd_flag} -Wall main.cc\n')
    p, state = init_pass(tmp_path, input_dir)
    assert state is not None

    assert load_ref_hints(state, b'@fileref') == {(b'main.cc', 0, 16, b'sub/foo.h')}


def test_unrelated_commands(tmp_path: Path):
    """Test that we don't run preprocessor on files only mentioned in non-compilation commands."""
    input_dir = tmp_path / 'test_case'
    input_dir.mkdir()
    (input_dir / 'good.cpp').write_text('#include "header.hpp"\n')
    (input_dir / 'header.hpp').touch()
    (input_dir / 'bad.cpp').write_text('#include "nonexisting.h"\n')
    (input_dir / 'makefile').write_text(
        """
a.out:
\tgcc good.cpp
foo.txt:
\tcat bad.cpp > foo.txt
        """
    )
    p, state = init_pass(tmp_path, input_dir)
    assert state is not None

    assert load_ref_hints(state, b'@fileref') == {(b'good.cpp', 0, 21, b'header.hpp')}


def test_unknown_flags(tmp_path: Path):
    """Test that we still get hints from the preprocessor even if unknown command-line flags are present."""
    input_dir = tmp_path / 'test_case'
    input_dir.mkdir()
    (input_dir / 'good.c').write_text('#include "header.h"\n')
    (input_dir / 'header.h').touch()
    (input_dir / 'makefile').write_text(
        """
a.out:
\tclang -foobar good.c -abacaba
        """
    )
    p, state = init_pass(tmp_path, input_dir)
    assert state is not None

    assert load_ref_hints(state, b'@fileref') == {(b'good.c', 0, 19, b'header.h')}


def test_some_commands_fail(tmp_path: Path):
    """Test that preprocessor failures on some of the files don't prevent us from reporting hints on others."""
    input_dir = tmp_path / 'test_case'
    input_dir.mkdir()
    (input_dir / 'good1.c').write_text('#include "good1.h"\n')
    (input_dir / 'good1.h').touch()
    (input_dir / 'bad.c').write_text('#include "nonexisting.h"\n')
    (input_dir / 'good2.c').write_text('#include "good2.h"\n')
    (input_dir / 'good2.h').touch()
    (input_dir / 'makefile').write_text(
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

    assert load_ref_hints(state, b'@fileref') == {
        (b'good1.c', 0, 18, b'good1.h'),
        (b'good2.c', 0, 18, b'good2.h'),
    }


def test_includes_from_outside(tmp_path: Path):
    """Test that we detect a header as used if it's included from a header not belonging to the test case."""
    input_dir = tmp_path / 'test_case'
    input_dir.mkdir()
    header_outside = tmp_path / 'outside.h'
    header_outside.write_text('#include "inside.h"')
    (input_dir / 'main.c').write_text(f'#include "{header_outside}"\n')
    (input_dir / 'inside.h').touch()
    (input_dir / 'makefile').write_text(
        """
a.out:
\tgcc -I. main.c
        """
    )
    p, state = init_pass(tmp_path, input_dir)
    assert state is not None

    assert load_ref_hints(state, b'@fileref') == {(None, None, None, b'inside.h')}


def test_clang_header_module(tmp_path: Path):
    """Test include detection for headers in a Clang header module."""
    input_dir = tmp_path / 'test_case'
    input_dir.mkdir()
    (input_dir / 'main.cc').write_text('#include "modular1.h"\n')
    (input_dir / 'modular1.h').write_text('#include "modular2.h"\n')
    (input_dir / 'modular2.h').write_text('#include "text.h"\n')
    (input_dir / 'text.h').touch()
    (input_dir / 'mod.cppmap').write_text(
        """
module mod {
    header "modular1.h"
    header "modular2.h"
}
        """
    )
    (input_dir / 'makefile').write_text(
        """
mod.pcm:
\tclang -xc++ -fmodules -Xclang -emit-module -fmodule-name=mod -c mod.cppmap -o mod.pcm
a.out: mod.pcm
\tclang -fmodules -fmodule-file=mod.pcm main.cc
        """
    )
    p, state = init_pass(tmp_path, input_dir)
    assert state is not None

    assert load_ref_hints(state, b'@fileref') == {
        (b'main.cc', 0, 21, b'modular1.h'),
        (b'modular1.h', 0, 21, b'modular2.h'),
        (b'modular2.h', 0, 17, b'text.h'),
    }


def test_clang_header_module_home_is_cwd(tmp_path: Path):
    """Test that headers in Clang header modules are discovered when -fmodule-map-file-home-is-cwd is used."""
    input_dir = tmp_path / 'test_case'
    input_dir.mkdir()
    (input_dir / 'sub').mkdir()
    (input_dir / 'sub' / 'modular.h').write_text('#include "text.h"\n')
    (input_dir / 'sub' / 'text.h').touch()
    (input_dir / 'another_sub').mkdir()
    (input_dir / 'another_sub' / 'mod.cppmap').write_text(
        """
module mod {
    header "sub/modular.h"
}
        """
    )
    (input_dir / 'makefile').write_text(
        """
mod.pcm:
\tclang -xc++ -fmodules -Xclang -emit-module -fmodule-name=mod -Xclang -fmodule-map-file-home-is-cwd -c another_sub/mod.cppmap -o mod.pcm
        """
    )
    p, state = init_pass(tmp_path, input_dir)
    assert state is not None

    assert load_ref_hints(state, b'@fileref') == {(b'sub/modular.h', 0, 17, b'sub/text.h')}

from pathlib import Path
from typing import Any

from cvise.passes.inlineincludes import InlineIncludesPass
from cvise.tests.testabstract import collect_all_transforms_dir, validate_stored_hints
from cvise.utils.hint import Hint, HintBundle, Patch
from cvise.utils.process import ProcessEventNotifier


def init_pass(
    tmp_dir: Path, input_path: Path, includes: list[tuple[Path, int, int, Path]]
) -> tuple[InlineIncludesPass, Any]:
    # Simulate the ClangIncludeGraphPass outputs.
    incl_bundle = HintBundle(vocabulary=[b'@c-include'], hints=[])
    for from_path, left, right, to_path in includes:
        incl_bundle.vocabulary.append(str(from_path.relative_to(input_path)).encode())
        incl_bundle.vocabulary.append(str(to_path.relative_to(input_path)).encode())
        incl_bundle.hints.append(
            Hint(
                type=0,
                patches=(Patch(path=len(incl_bundle.vocabulary) - 2, left=left, right=right),),
                extra=len(incl_bundle.vocabulary) - 1,
            )
        )

    # Initialize the main pass.
    pass_ = InlineIncludesPass()
    state = pass_.new(
        input_path, tmp_dir=tmp_dir, process_event_notifier=ProcessEventNotifier(None), dependee_hints=[incl_bundle]
    )
    validate_stored_hints(state, pass_, input_path)
    return pass_, state


def test_inclusion_single_header(tmp_path: Path):
    """Verifies the #include gets replaced with the header's contents, for the header not used elsewhere."""
    input_dir = tmp_path / 'test_case'
    input_dir.mkdir()
    (input_dir / 'head.h').write_text('int foo;\nint bar;\n')
    include = '#include "head.h"'
    (input_dir / 'main.cc').write_text(include + '\nint x = foo;\n')
    p, state = init_pass(tmp_path, input_dir, [(input_dir / 'main.cc', 0, len(include), input_dir / 'head.h')])
    assert state is not None
    all_transforms = collect_all_transforms_dir(p, state, input_dir)

    assert (('head.h', b''), ('main.cc', b'int foo;\nint bar;\n\nint x = foo;\n')) in all_transforms


def test_no_inclusion_header_used_in_multiple_places(tmp_path: Path):
    """Verifies no #include replacement happens when the header is used in multiple places."""
    input_dir = tmp_path / 'test_case'
    input_dir.mkdir()
    (input_dir / 'head.h').write_text('int foo;\nint bar;\n')
    include = '#include "head.h"'
    (input_dir / 'a.cc').write_text(include)
    (input_dir / 'b.cc').write_text(include)
    p, state = init_pass(
        tmp_path,
        input_dir,
        [
            (input_dir / 'a.cc', 0, len(include), input_dir / 'head.h'),
            (input_dir / 'b.cc', 0, len(include), input_dir / 'head.h'),
        ],
    )
    assert state is None


def test_inclusion_header_chain(tmp_path: Path):
    """Verifies we don't try moving header's old contexts while simultaneously moving other header into itself.

    We want to forbid this because such cross-file chains of changes aren't supported, and in the current implementation
    the mid-way changes would be lost.
    """
    input_dir = tmp_path / 'test_case'
    input_dir.mkdir()
    (input_dir / 'a.h').write_text('int x;\n')
    include_a = '#include "a.h"'
    (input_dir / 'b.h').write_text(include_a + '\n')
    include_b = '#include "b.h"'
    (input_dir / 'c.h').write_text(include_b + '\n')
    p, state = init_pass(
        tmp_path,
        input_dir,
        [
            (input_dir / 'b.h', 0, len(include_a), input_dir / 'a.h'),
            (input_dir / 'c.h', 0, len(include_b), input_dir / 'b.h'),
        ],
    )
    all_transforms = collect_all_transforms_dir(p, state, input_dir)

    # "a.h" moved into "b.h"
    assert (('a.h', b''), ('b.h', b'int x;\n\n'), ('c.h', b'#include "b.h"\n')) in all_transforms
    # "b.h" moved into "c.h"
    assert (('a.h', b'int x;\n'), ('b.h', b''), ('c.h', b'#include "a.h"\n\n')) in all_transforms
    # no change that loses the original code from a.h
    assert (('a.h', b''), ('b.h', b''), ('c.h', b'#include "a.h"\n\n')) not in all_transforms

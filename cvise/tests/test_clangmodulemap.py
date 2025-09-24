from pathlib import Path
import pytest
from typing import Any, Tuple

from cvise.passes.clangmodulemap import ClangModuleMapPass
from cvise.tests.testabstract import collect_all_transforms_dir, validate_stored_hints
from cvise.utils.hint import load_hints
from cvise.utils.process import ProcessEventNotifier


@pytest.fixture
def test_case_path(tmp_path: Path) -> Path:
    path = tmp_path / 'test_case'
    path.mkdir()
    return path


def init_pass(tmp_dir: Path, test_case_path: Path) -> Tuple[ClangModuleMapPass, Any]:
    pass_ = ClangModuleMapPass()
    state = pass_.new(
        test_case_path, tmp_dir=tmp_dir, process_event_notifier=ProcessEventNotifier(None), dependee_hints=[]
    )
    validate_stored_hints(state, pass_, test_case_path)
    return pass_, state


def test_make_header_non_modular(tmp_path: Path, test_case_path: Path):
    (test_case_path / 'A.modulemap').write_text(
        """
            module "some_module" {
                export *
                header "foo.h"
            }
        """,
    )
    (test_case_path / 'B.cppmap').write_text(
        """
            module "some_module" {
                export *
                textual header "bar.h"
                private textual header "baz.h"
            }
        """,
    )
    p, state = init_pass(tmp_path, test_case_path)
    all_transforms = collect_all_transforms_dir(p, state, test_case_path)

    assert (
        (
            'A.modulemap',
            b"""
            module "some_module" {
                export *
            }
        """,
        ),
        (
            'B.cppmap',
            b"""
            module "some_module" {
                export *
            }
        """,
        ),
    ) in all_transforms
    # check that we can also delete some but not all headers (no need to test all possible combinations)
    assert (
        (
            'A.modulemap',
            b"""
            module "some_module" {
                export *
                header "foo.h"
            }
        """,
        ),
        (
            'B.cppmap',
            b"""
            module "some_module" {
                export *
                private textual header "baz.h"
            }
        """,
        ),
    ) in all_transforms


def test_make_header_non_modular_nested(tmp_path: Path, test_case_path: Path):
    (test_case_path / 'A.modulemap').write_text(
        """
            module "//some" {
                module "//some/B" {
                    header "foo.h"
                }
                module "//some/C" {
                    header "bar.h"
                }
            }
            module "//other" {
                module "//other/D" {
                    header "baz.h"
                }
            }
        """,
    )
    p, state = init_pass(tmp_path, test_case_path)
    all_transforms = collect_all_transforms_dir(p, state, test_case_path)

    assert (
        (
            'A.modulemap',
            b"""
            module "//some" {
                module "//some/B" {
                }
                module "//some/C" {
                }
            }
            module "//other" {
                module "//other/D" {
                }
            }
        """,
        ),
    ) in all_transforms


def test_delete_use_decl(tmp_path: Path, test_case_path: Path):
    (test_case_path / 'A.modulemap').write_text(
        """
            module "//some" {
                header "foo.h"
                use "//other/X"
                header "bar.h"
                use "//other/Y"
            }
        """,
    )
    p, state = init_pass(tmp_path, test_case_path)
    all_transforms = collect_all_transforms_dir(p, state, test_case_path)

    assert (
        (
            'A.modulemap',
            b"""
            module "//some" {
                header "foo.h"
                header "bar.h"
            }
        """,
        ),
    ) in all_transforms


def test_delete_empty_submodule(tmp_path: Path, test_case_path: Path):
    (test_case_path / 'A.modulemap').write_text(
        """
            module "A" {
                module "A_inner" {
                }
            }
            module "B" {
            }
            module "C" {
                module "C_inner" {
                }
            }
        """,
    )
    p, state = init_pass(tmp_path, test_case_path)
    all_transforms = collect_all_transforms_dir(p, state, test_case_path)

    # Check that empty submodules, but not the top-level module, were attempted to be deleted.
    assert (
        (
            'A.modulemap',
            b"""
            module "A" {
            }
            module "B" {
            }
            module "C" {
            }
        """,
        ),
    ) in all_transforms


def test_inline_submodule_contents(tmp_path: Path, test_case_path: Path):
    (test_case_path / 'A.modulemap').write_text(
        """
            module "A" {
                header "a.h"
                module "B" {
                    header "b.h"
                    module "C" {
                        header "c.h"
                    }
                }
            }
        """,
    )
    p, state = init_pass(tmp_path, test_case_path)
    all_transforms = collect_all_transforms_dir(p, state, test_case_path)

    # "C" inlined into "B":
    assert (
        (
            'A.modulemap',
            b"""
            module "A" {
                header "a.h"
                module "B" {
                    header "b.h"
                        header "c.h"
                }
            }
        """,
        ),
    ) in all_transforms
    # "B" inlined into "A":
    assert (
        (
            'A.modulemap',
            b"""
            module "A" {
                header "a.h"
                    header "b.h"
                    module "C" {
                        header "c.h"
                    }
            }
        """,
        ),
    ) in all_transforms


def test_unrelated_files(tmp_path: Path, test_case_path: Path):
    (test_case_path / 'A.txt').write_text('Hello\n')
    (test_case_path / 'B.modulemap').write_text(
        """
            module "A" {
                header "a.h"
            }
        """,
    )
    (test_case_path / 'Makefile').write_text('.PHONY: foo\n')
    (test_case_path / 'X.modulemap').write_text(
        """
            module "X" {
                header "x.h"
            }
        """,
    )
    p, state = init_pass(tmp_path, test_case_path)
    all_transforms = collect_all_transforms_dir(p, state, test_case_path)

    assert (
        ('A.txt', b'Hello\n'),
        (
            'B.modulemap',
            b"""
            module "A" {
            }
        """,
        ),
        ('Makefile', b'.PHONY: foo\n'),
        (
            'X.modulemap',
            b"""
            module "X" {
            }
        """,
        ),
    ) in all_transforms


def test_delete_blank_lines(tmp_path: Path, test_case_path: Path):
    (test_case_path / 'A.cppmap').write_text(
        """module "A" {

                header "a.h"

            }""",
    )
    p, state = init_pass(tmp_path, test_case_path)
    all_transforms = collect_all_transforms_dir(p, state, test_case_path)

    assert (
        (
            'A.cppmap',
            b"""module "A" {
                header "a.h"
            }""",
        ),
    ) in all_transforms


def test_delete_exports(tmp_path: Path, test_case_path: Path):
    (test_case_path / 'A.cppmap').write_text(
        """module "A" {
                export *
                header "a.h"
                export *
            }""",
    )
    p, state = init_pass(tmp_path, test_case_path)
    all_transforms = collect_all_transforms_dir(p, state, test_case_path)

    assert (
        (
            'A.cppmap',
            b"""module "A" {
                header "a.h"
            }""",
        ),
    ) in all_transforms


def test_fileref(tmp_path: Path, test_case_path: Path):
    (test_case_path / 'A.modulemap').write_text(
        """
            module "some_module" {
                header "a.h"
                header "nonexisting.h"
                module "nested" {
                    header "b.h"
                }
            }
        """,
    )
    (test_case_path / 'a.h').touch()
    (test_case_path / 'b.h').touch()
    p, state = init_pass(tmp_path, test_case_path)
    bundle_paths = state.hint_bundle_paths()

    assert b'@fileref' in bundle_paths
    bundle = load_hints(bundle_paths[b'@fileref'], None, None)
    refs = {bundle.vocabulary[h.extra] for h in bundle.hints}
    assert refs == {b'a.h', b'b.h'}

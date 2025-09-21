from pathlib import Path
import pytest
from typing import Any, Tuple

from cvise.passes.makefile import MakefilePass
from cvise.tests.testabstract import collect_all_transforms_dir, validate_stored_hints
from cvise.utils.process import ProcessEventNotifier


@pytest.fixture
def test_case_path(tmp_path: Path) -> Path:
    path = tmp_path / 'test_case'
    path.mkdir()
    return path


def init_pass(tmp_dir: Path, test_case_path: Path) -> Tuple[MakefilePass, Any]:
    pass_ = MakefilePass()
    state = pass_.new(
        test_case_path, tmp_dir=tmp_dir, process_event_notifier=ProcessEventNotifier(None), dependee_hints=[]
    )
    validate_stored_hints(state, pass_)
    return pass_, state


def test_remove_argument(tmp_path: Path, test_case_path: Path):
    (test_case_path / 'Makefile').write_text(
        """
a.out:
\tgcc -Wall foo.c
        """,
    )
    p, state = init_pass(tmp_path, test_case_path)
    all_transforms = collect_all_transforms_dir(p, state, test_case_path)

    # "-Wall" removed
    assert (
        (
            'Makefile',
            b"""
a.out:
\tgcc  foo.c
        """,
        ),
    ) in all_transforms
    # program name ("gcc") not removed
    assert (
        (
            'Makefile',
            b"""
a.out:
\t -Wall foo.c
        """,
        ),
    ) not in all_transforms


def test_dont_remove_file_argument(tmp_path: Path, test_case_path: Path):
    (test_case_path / 'Makefile').write_text(
        """
a.o:
\tgcc -o a.o foo.c
b.o:
\tgcc -ob.o bar.c
        """,
    )
    p, state = init_pass(tmp_path, test_case_path)
    all_transforms = collect_all_transforms_dir(p, state, test_case_path)

    # "-o a.o" not removed
    assert (
        (
            'Makefile',
            b"""
a.out:
\tgcc   foo.c
b.o:
\tgcc -ob.o bar.c
        """,
        ),
    ) not in all_transforms
    # "-o" not removed
    assert (
        (
            'Makefile',
            b"""
a.out:
\tgcc  a.o foo.c
b.o:
\tgcc -ob.o bar.c
        """,
        ),
    ) not in all_transforms
    # "a.o" not removed
    assert (
        (
            'Makefile',
            b"""
a.out:
\tgcc -o  foo.c
b.o:
\tgcc -ob.o bar.c
        """,
        ),
    ) not in all_transforms
    # "-ob.o" not removed
    assert (
        (
            'Makefile',
            b"""
a.o:
\tgcc -o a.o foo.c
b.o:
\tgcc  bar.c
        """,
        ),
    ) not in all_transforms


def test_remove_argument_from_all_commands(tmp_path: Path, test_case_path: Path):
    (test_case_path / 'makefile').write_text(
        """
a.out:
\tgcc -Wall foo.c
b.out:
\tgcc -Werror -Wall -o b.out bar.c
        """,
    )
    p, state = init_pass(tmp_path, test_case_path)
    all_transforms = collect_all_transforms_dir(p, state, test_case_path)

    assert (
        (
            'makefile',
            b"""
a.out:
\tgcc  foo.c
b.out:
\tgcc -Werror  -o b.out bar.c
        """,
        ),
    ) in all_transforms

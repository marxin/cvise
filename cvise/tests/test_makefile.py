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
    validate_stored_hints(state, pass_, test_case_path)
    return pass_, state


def test_remove_argument(tmp_path: Path, test_case_path: Path):
    (test_case_path / 'Makefile').write_text(
        """
a.out:
\tgcc -ansi foo.c
        """,
    )
    p, state = init_pass(tmp_path, test_case_path)
    all_transforms = collect_all_transforms_dir(p, state, test_case_path)

    # "-ansi" removed
    assert (
        (
            'Makefile',
            b"""
a.out:
\tgcc foo.c
        """,
        ),
    ) in all_transforms
    # program name ("gcc") not removed
    assert (
        (
            'Makefile',
            b"""
a.out:
\t -ansi foo.c
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
\tgcc foo.c
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
\tgcc a.o foo.c
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
\tgcc -o foo.c
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
\tgcc bar.c
        """,
        ),
    ) not in all_transforms


def test_dont_remove_blocklisted_argument(tmp_path: Path, test_case_path: Path):
    (test_case_path / 'Makefile').write_text(
        """
a.o:
\tgcc -Wall foo.c
        """,
    )
    p, state = init_pass(tmp_path, test_case_path)
    all_transforms = collect_all_transforms_dir(p, state, test_case_path)

    # "-Wall" not removed
    assert (
        (
            'Makefile',
            b"""
a.o:
\tgcc foo.c
        """,
        ),
    ) not in all_transforms


def test_remove_argument_from_all_commands(tmp_path: Path, test_case_path: Path):
    (test_case_path / 'makefile').write_text(
        """
a.out:
\tgcc -ansi foo.c
b.out:
\tgcc -fsigned-char -ansi -o b.out bar.c
        """,
    )
    p, state = init_pass(tmp_path, test_case_path)
    all_transforms = collect_all_transforms_dir(p, state, test_case_path)

    # "-ansi" removed from all commands
    assert (
        (
            'makefile',
            b"""
a.out:
\tgcc foo.c
b.out:
\tgcc -fsigned-char -o b.out bar.c
        """,
        ),
    ) in all_transforms


def test_continuation(tmp_path: Path, test_case_path: Path):
    (test_case_path / 'makefile').write_text(
        """
a.out:
\tgcc -ansi foo.c
b.out: \\
    a.out
\tgcc \\
\t    -fsigned-char \\
\t    -ansi \\
\t    -o b.out bar.c
        """,
    )
    p, state = init_pass(tmp_path, test_case_path)
    all_transforms = collect_all_transforms_dir(p, state, test_case_path)

    # "-ansi" removed from all commands
    assert (
        (
            'makefile',
            b"""
a.out:
\tgcc foo.c
b.out: \\
    a.out
\tgcc \\
\t    -fsigned-char \\
\t    -o b.out bar.c
        """,
        ),
    ) in all_transforms


def test_argument_with_escaped_quotes(tmp_path: Path, test_case_path: Path):
    (test_case_path / 'Makefile').write_text(
        """
a.o:
\tgcc -Dfoo=\\"x y\\" foo.c
        """,
    )
    p, state = init_pass(tmp_path, test_case_path)
    all_transforms = collect_all_transforms_dir(p, state, test_case_path)

    # -D... removed
    assert (
        (
            'Makefile',
            b"""
a.o:
\tgcc foo.c
        """,
        ),
    ) in all_transforms
    # the argument isn't half-removed
    assert (
        (
            'Makefile',
            b"""
a.o:
\tgcc -Dfoo=\\"x  foo.c
        """,
        ),
    ) not in all_transforms
    assert (
        (
            'Makefile',
            b"""
a.o:
\tgcc  y\\" foo.c
        """,
        ),
    ) not in all_transforms


def test_argument_with_nested_quotes(tmp_path: Path, test_case_path: Path):
    (test_case_path / 'Makefile').write_text(
        """
a.o:
\tgcc '-Dfoo="x y"' foo.c
        """,
    )
    p, state = init_pass(tmp_path, test_case_path)
    all_transforms = collect_all_transforms_dir(p, state, test_case_path)

    # -D... removed
    assert (
        (
            'Makefile',
            b"""
a.o:
\tgcc foo.c
        """,
        ),
    ) in all_transforms
    # the argument isn't partially-removed
    assert (
        (
            'Makefile',
            b"""
a.o:
\tgcc '-Dfoo="x foo.c
        """,
        ),
    ) not in all_transforms
    assert (
        (
            'Makefile',
            b"""
a.o:
\tgcc y"' foo.c
        """,
        ),
    ) not in all_transforms
    assert (
        (
            'Makefile',
            b"""
a.o:
\tgcc '-Dfoo=' foo.c
        """,
        ),
    ) not in all_transforms


def test_remove_target(tmp_path: Path, test_case_path: Path):
    (test_case_path / 'Makefile').write_text(
        """
prog: a.o b.o
\tgcc -o prog a.o b.o
a.o:
\tgcc -o a.o a.c
b.o:
\tgcc -o b.o b.c""",
    )
    p, state = init_pass(tmp_path, test_case_path)
    all_transforms = collect_all_transforms_dir(p, state, test_case_path)

    # "a.o" removed
    assert (
        (
            'Makefile',
            b"""
prog: b.o
\tgcc -o prog b.o
b.o:
\tgcc -o b.o b.c""",
        ),
    ) in all_transforms
    # "b.o" removed
    assert (
        (
            'Makefile',
            b"""
prog: a.o
\tgcc -o prog a.o
a.o:
\tgcc -o a.o a.c\n""",
        ),
    ) in all_transforms


def test_remove_target_precompiled_module(tmp_path: Path, test_case_path: Path):
    (test_case_path / 'Makefile').write_text(
        """
a.out: mod.pcm
\tclang -fmodules -fmodule-file=mod.pcm main.cc
mod.pcm:
\tclang -fmodules -Xclang -emit-module -fmodule-name=mod mod.cppmap -o mod.pcm
        """,
    )
    p, state = init_pass(tmp_path, test_case_path)
    all_transforms = collect_all_transforms_dir(p, state, test_case_path)

    # "mod.pcm" removed
    assert (
        (
            'Makefile',
            b"""
a.out:
\tclang -fmodules main.cc\n""",
        ),
    ) in all_transforms


def test_dont_remove_phony_target(tmp_path: Path, test_case_path: Path):
    (test_case_path / 'Makefile').write_text(
            """
.PHONY: all clean
all: a.out
a.out:
\tgcc main.c
clean:
\trm -f a.out
            """,
    )
    p, state = init_pass(tmp_path, test_case_path)
    all_transforms = collect_all_transforms_dir(p, state, test_case_path)

    # "a.out" removed
    assert (
        (
            'Makefile',
            b"""
.PHONY: all clean
all:
clean:
\trm -f
            """
        ),
    ) in all_transforms
    # "all" not removed
    assert (
        (
            'Makefile',
            b"""
.PHONY: clean
a.out:
\tgcc main.c
clean:
\trm -f a.out
            """
        ),
    ) not in all_transforms
    # "clean" not removed
    assert (
        (
            'Makefile',
            b"""
.PHONY: all
all: a.out
a.out:
\tgcc main.c
            """
        ),
    ) not in all_transforms

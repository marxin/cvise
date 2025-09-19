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


def test_remove_target(tmp_path: Path, test_case_path: Path):
    (test_case_path / 'Makefile').write_text(
        """
a.o:
\tgcc -barbaz foo.c
        """,
    )
    p, state = init_pass(tmp_path, test_case_path)
    all_transforms = collect_all_transforms_dir(p, state, test_case_path)

    assert (
        (
            'Makefile',
            b"""
a.o:
\tgcc  foo.c
        """,
        ),
    ) in all_transforms

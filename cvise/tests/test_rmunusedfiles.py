from pathlib import Path
import pytest
from typing import Any, List, Tuple

from cvise.passes.rmunusedfiles import RmUnusedFilesPass
from cvise.tests.testabstract import collect_all_transforms_dir, validate_stored_hints
from cvise.utils.hint import Hint, HintBundle, Patch
from cvise.utils.process import ProcessEventNotifier


@pytest.fixture
def test_case_path(tmp_path: Path) -> Path:
    path = tmp_path / 'test_case'
    path.mkdir()
    return path


def init_pass(tmp_dir: Path, test_case_path: Path, dependee_hints: List[HintBundle]) -> Tuple[RmUnusedFilesPass, Any]:
    pass_ = RmUnusedFilesPass()
    state = pass_.new(
        test_case_path,
        tmp_dir=tmp_dir,
        process_event_notifier=ProcessEventNotifier(None),
        dependee_hints=dependee_hints,
    )
    validate_stored_hints(state, pass_, test_case_path)
    return pass_, state


def test_unused_files_deleted(tmp_path: Path, test_case_path: Path):
    (test_case_path / 'main.c').write_text('r')
    (test_case_path / 'foo.h').touch()
    (test_case_path / 'bar.h').touch()
    (test_case_path / 'z.h').touch()
    # Fake filerefs from main.c to bar.h and from unspecified location to main.c.
    filerefs_bundle = HintBundle(
        hints=[
            Hint(type=0, patches=[Patch(left=0, right=1, file=1)], extra=2),
            Hint(type=0, patches=[], extra=1),
        ],
        vocabulary=[b'@fileref', b'main.c', b'bar.h'],
    )
    p, state = init_pass(tmp_path, test_case_path, dependee_hints=[filerefs_bundle])
    all_transforms = collect_all_transforms_dir(p, state, test_case_path)

    # foo.h and z.h deleted
    assert (
        (
            'bar.h',
            b'',
        ),
        (
            'main.c',
            b'r',
        ),
    ) in all_transforms

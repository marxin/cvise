from pathlib import Path
import pytest
from typing import Any

from cvise.passes.abstract import PassResult
from cvise.passes.rmunusedfiles import RmUnusedFilesPass
from cvise.tests.testabstract import collect_all_transforms_dir, validate_stored_hints
from cvise.utils.hint import Hint, HintBundle, Patch
from cvise.utils.process import ProcessEventNotifier


@pytest.fixture
def test_case_path(tmp_path: Path) -> Path:
    path = tmp_path / 'test_case'
    path.mkdir()
    return path


def init_pass(tmp_dir: Path, test_case_path: Path, dependee_hints: list[HintBundle]) -> tuple[RmUnusedFilesPass, Any]:
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
    (test_case_path / 'a.c').write_text('r')
    (test_case_path / 'bar.h').touch()
    (test_case_path / 'foo.h').touch()
    (test_case_path / 'z.h').touch()
    # Fake filerefs from a.c to foo.h and from unspecified location to a.c.
    filerefs_bundle = HintBundle(
        hints=[
            Hint(type=0, patches=(Patch(left=0, right=1, path=1),), extra=2),
            Hint(type=0, patches=(), extra=1),
        ],
        vocabulary=[b'@fileref', b'a.c', b'foo.h'],
    )
    p, state = init_pass(tmp_path, test_case_path, dependee_hints=[filerefs_bundle])
    all_transforms = collect_all_transforms_dir(p, state, test_case_path)

    # bar.h and z.h deleted
    assert (
        (
            'a.c',
            b'r',
        ),
        (
            'foo.h',
            b'',
        ),
    ) in all_transforms
    # bar.h deleted
    assert (
        (
            'a.c',
            b'r',
        ),
        (
            'foo.h',
            b'',
        ),
        (
            'z.h',
            b'',
        ),
    ) in all_transforms
    # z.h deleted
    assert (
        (
            'a.c',
            b'r',
        ),
        (
            'bar.h',
            b'',
        ),
        (
            'foo.h',
            b'',
        ),
    ) in all_transforms


def test_unused_empty_dirs_deleted(tmp_path: Path, test_case_path: Path):
    (test_case_path / 'a').mkdir()
    (test_case_path / 'b').mkdir()
    (test_case_path / 'b' / 'foo.txt').touch()
    (test_case_path / 'c').mkdir()
    (test_case_path / 'd').mkdir()
    (test_case_path / 'd' / 'e').mkdir()
    # Fake filerefs to "c".
    filerefs_bundle = HintBundle(
        hints=[Hint(type=0, patches=(), extra=1)],
        vocabulary=[b'@fileref', b'c'],
    )
    p, state = init_pass(tmp_path, test_case_path, dependee_hints=[filerefs_bundle])
    out_path = tmp_path / 'out'

    result, _new_state = p.transform(
        out_path,
        state,
        process_event_notifier=ProcessEventNotifier(None),
        original_test_case=test_case_path,
        written_paths=set(),
    )

    assert result == PassResult.OK
    # "a" and "e" deleted
    assert set(out_path.rglob('*')) == {out_path / 'b', out_path / 'b' / 'foo.txt', out_path / 'c', out_path / 'd'}

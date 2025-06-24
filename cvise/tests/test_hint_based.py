import jsonschema
from pathlib import Path
from typing import Dict, Sequence

from cvise.passes.hint_based import HintBasedPass
from cvise.tests.testabstract import collect_all_transforms, iterate_pass
from cvise.utils.hint import HINT_SCHEMA


class StubHintBasedPass(HintBasedPass):
    def __init__(self, contents_to_hints: Dict[str, Sequence[object]]):
        super().__init__()
        self.contents_to_hints = contents_to_hints

    def generate_hints(self, test_case: Path) -> Sequence[object]:
        contents = test_case.read_text()
        return self.contents_to_hints.get(contents, [])


def test_hint_based_first_char_once(tmp_path: Path):
    """Test the case of a sole hint."""
    hint = {'p': [{'l': 0, 'r': 1}]}
    jsonschema.validate(hint, schema=HINT_SCHEMA)
    pass_ = StubHintBasedPass(
        {
            'foo': [hint],
            'oo': [],
        }
    )
    test_case = tmp_path / 'input.txt'
    test_case.write_text('foo')

    iterate_pass(pass_, test_case, temp_dir=tmp_path)

    assert test_case.read_text() == 'oo'


def test_hint_based_last_char_repeatedly(tmp_path: Path):
    """Test the case of applying a single hint that's different every time."""
    hint0 = {'p': [{'l': 0, 'r': 1}]}
    hint1 = {'p': [{'l': 1, 'r': 2}]}
    hint2 = {'p': [{'l': 2, 'r': 3}]}
    for h in hint0, hint1, hint2:
        jsonschema.validate(h, schema=HINT_SCHEMA)
    pass_ = StubHintBasedPass(
        {
            'foo': [hint2],
            'fo': [hint1],
            'f': [hint0],
        }
    )
    test_case = tmp_path / 'input.txt'
    test_case.write_text('foo')

    iterate_pass(pass_, test_case, temp_dir=tmp_path)

    assert test_case.read_text() == ''


def test_hint_based_all_chars_grouped(tmp_path: Path):
    """Test the case of multiple hints to be picked up together as a group.

    Currently, the grouping behavior is implemented as a binary search."""
    hint1 = {'p': [{'l': 0, 'r': 1}]}
    hint2 = {'p': [{'l': 1, 'r': 2}]}
    hint3 = {'p': [{'l': 2, 'r': 3}]}
    for h in hint1, hint2, hint3:
        jsonschema.validate(h, schema=HINT_SCHEMA)
    pass_ = StubHintBasedPass(
        {
            'foo': [hint1, hint2, hint3],
        }
    )
    test_case = tmp_path / 'input.txt'
    test_case.write_text('foo')

    iterate_pass(pass_, test_case, temp_dir=tmp_path)

    assert test_case.read_text() == ''


def test_hint_based_state_iteration(tmp_path: Path):
    """Test advancing through multiple hints.

    Unlike iterate_pass-based tests which pretend that any transformation leads
    to a successful interestingness test and proceed immediately, here we
    verify how different hints are attempted."""
    hint0 = {'p': [{'l': 0, 'r': 1}]}
    hint1 = {'p': [{'l': 1, 'r': 2}]}
    hint3 = {'p': [{'l': 3, 'r': 4}]}
    hint4 = {'p': [{'l': 4, 'r': 5}]}
    for h in hint0, hint1, hint3, hint4:
        jsonschema.validate(h, schema=HINT_SCHEMA)
    pass_ = StubHintBasedPass(
        {
            'ab cd': [hint0, hint1, hint3, hint4],
        }
    )
    test_case = tmp_path / 'input.txt'
    test_case.write_text('ab cd')

    state = pass_.new(test_case, temp_dir=tmp_path)
    all_transforms = collect_all_transforms(pass_, state, test_case)
    assert 'b cd' in all_transforms  # hint0 applied
    assert 'a cd' in all_transforms  # hint1 applied
    assert 'ab d' in all_transforms  # hint3 applied
    assert 'ab c' in all_transforms  # hint4 applied
    assert ' ' in all_transforms  # all hints applied

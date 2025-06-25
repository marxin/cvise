import jsonschema
from pathlib import Path
from typing import Dict, Sequence

from cvise.passes.hint_based import HintBasedPass
from cvise.tests.testabstract import collect_all_transforms, iterate_pass
from cvise.utils.hint import HINT_SCHEMA


class StubHintBasedPass(HintBasedPass):
    def __init__(self, contents_to_hints: Dict[str, Sequence[object]]):
        super().__init__()
        for hints in contents_to_hints.values():
            for hint in hints:
                jsonschema.validate(hint, schema=HINT_SCHEMA)
        self.contents_to_hints = contents_to_hints

    def generate_hints(self, test_case: Path) -> Sequence[object]:
        contents = test_case.read_text()
        return self.contents_to_hints.get(contents, [])


def test_hint_based_first_char_once(tmp_path: Path):
    """Test the case of a single hint."""
    hint = {'p': [{'l': 0, 'r': 1}]}
    pass_ = StubHintBasedPass(
        {
            'foo': [hint],
        }
    )
    test_case = tmp_path / 'input.txt'
    test_case.write_text('foo')

    iterate_pass(pass_, test_case, tmp_dir=tmp_path)

    assert test_case.read_text() == 'oo'


def test_hint_based_last_char_repeatedly(tmp_path: Path):
    """Test the case of applying a single hint that's different every time."""
    hint_byte0 = {'p': [{'l': 0, 'r': 1}]}
    hint_byte1 = {'p': [{'l': 1, 'r': 2}]}
    hint_byte2 = {'p': [{'l': 2, 'r': 3}]}
    pass_ = StubHintBasedPass(
        {
            'foo': [hint_byte2],
            'fo': [hint_byte1],
            'f': [hint_byte0],
        }
    )
    test_case = tmp_path / 'input.txt'
    test_case.write_text('foo')

    iterate_pass(pass_, test_case, tmp_dir=tmp_path)

    assert test_case.read_text() == ''


def test_hint_based_all_chars_grouped(tmp_path: Path):
    """Test the case of multiple hints to be picked up together as a group.

    The logic that chooses ranges of hints to be attempted (the binary search)
    is mostly irrelevant for the test - we only expect it to try *all* hints
    together."""
    hint_byte0 = {'p': [{'l': 0, 'r': 1}]}
    hint_byte1 = {'p': [{'l': 1, 'r': 2}]}
    hint_byte2 = {'p': [{'l': 2, 'r': 3}]}
    pass_ = StubHintBasedPass(
        {
            'foo': [hint_byte0, hint_byte1, hint_byte2],
        }
    )
    test_case = tmp_path / 'input.txt'
    test_case.write_text('foo')

    iterate_pass(pass_, test_case, tmp_dir=tmp_path)

    assert test_case.read_text() == ''


def test_hint_based_state_iteration(tmp_path: Path):
    """Test advancing through multiple hints.

    Unlike iterate_pass-based tests which pretend that any transformation leads
    to a successful interestingness test and proceed immediately, here we
    verify how different hints are attempted."""
    hint_bytes01 = {'p': [{'l': 0, 'r': 2}]}
    hint_bytes12 = {'p': [{'l': 1, 'r': 3}]}
    hint_bytes45 = {'p': [{'l': 4, 'r': 6}]}
    hint_bytes2345 = {'p': [{'l': 2, 'r': 6}]}
    pass_ = StubHintBasedPass(
        {
            'abc def': [hint_bytes01, hint_bytes12, hint_bytes45, hint_bytes2345],
        }
    )
    test_case = tmp_path / 'input.txt'
    test_case.write_text('abc def')

    state = pass_.new(test_case, tmp_dir=tmp_path)
    all_transforms = collect_all_transforms(pass_, state, test_case)
    assert 'c def' in all_transforms  # 01 applied
    assert 'a def' in all_transforms  # 12 applied
    assert 'abc f' in all_transforms  # 45 applied
    assert 'abf' in all_transforms  # 2345 applied (also 45+2345, with the same result)
    assert ' def' in all_transforms  # 01+12 applied
    assert 'f' in all_transforms  # all hints applied

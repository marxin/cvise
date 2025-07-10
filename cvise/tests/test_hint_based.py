import jsonschema
from pathlib import Path
from typing import Dict, List, Sequence, Union

from cvise.passes.hint_based import HintBasedPass
from cvise.tests.testabstract import collect_all_transforms, iterate_pass
from cvise.utils.hint import HintBundle, HINT_SCHEMA


class StubHintBasedPass(HintBasedPass):
    def __init__(self, contents_to_hints: Dict[str, Sequence[object]], vocabulary: Union[List[str], None] = None):
        super().__init__()
        for hints in contents_to_hints.values():
            for hint in hints:
                jsonschema.validate(hint, schema=HINT_SCHEMA)
        self.contents_to_hints = contents_to_hints
        self.vocabulary = vocabulary or []

    def generate_hints(self, test_case: Path) -> HintBundle:
        contents = test_case.read_text()
        hints = self.contents_to_hints.get(contents, [])
        return HintBundle(vocabulary=self.vocabulary, hints=hints)


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


def test_hint_based_multiple_types(tmp_path: Path):
    """Test advancing through hints of multiple types."""
    vocab = ['space_removal', 'b_removal']
    hint_space1 = {'t': 0, 'p': [{'l': 3, 'r': 4}]}
    hint_space2 = {'t': 0, 'p': [{'l': 7, 'r': 8}]}
    hint_b1 = {'t': 1, 'p': [{'l': 1, 'r': 2}]}
    hint_b2 = {'t': 1, 'p': [{'l': 6, 'r': 7}]}
    pass_ = StubHintBasedPass(
        {
            'aba cab a': [hint_b1, hint_space1, hint_b2, hint_space2],
        },
        vocabulary=vocab,
    )
    test_case = tmp_path / 'input.txt'
    test_case.write_text('aba cab a')

    state = pass_.new(test_case, tmp_dir=tmp_path)
    all_transforms = collect_all_transforms(pass_, state, test_case)
    assert 'abacab a' in all_transforms  # space1 applied
    assert 'aba caba' in all_transforms  # space2 applied
    assert 'abacaba' in all_transforms  # space1&2 applied
    assert 'aa cab a' in all_transforms  # hint_b1 applied
    assert 'aba ca a' in all_transforms  # hint_b2 applied
    assert 'aa ca a' in all_transforms  # hint_b1&2 applied


def test_hint_based_type1_fewer_than_type2(tmp_path: Path):
    """Test the scenario there are two hint types, with fewer hints for the first type.

    Verify that subranges of same-typed hints are checked, but differently-typed hints aren't mixed.
    """
    vocab = ['type0', 'type1']
    hint1 = {'t': 0, 'p': [{'l': 0, 'r': 1}]}
    hint2 = {'t': 1, 'p': [{'l': 1, 'r': 2}]}
    hint3 = {'t': 1, 'p': [{'l': 2, 'r': 3}]}
    pass_ = StubHintBasedPass(
        {
            'abc': [hint1, hint2, hint3],
        },
        vocabulary=vocab,
    )
    test_case = tmp_path / 'input.txt'
    test_case.write_text('abc')

    state = pass_.new(test_case, tmp_dir=tmp_path)
    all_transforms = collect_all_transforms(pass_, state, test_case)
    assert 'bc' in all_transforms  # hint1 applied
    assert 'a' in all_transforms  # hint2&3 applied
    assert 'c' not in all_transforms  # no attempt to apply different-typed hint1 and hint2
    assert 'b' not in all_transforms  # no attempt to apply different-typed hint1 and hint3


def test_hint_based_type2_fewer_than_type1(tmp_path: Path):
    """Test the scenario there are two hint types, with fewer hints for the second type.

    Verify that subranges of same-typed hints are checked, but differently-typed hints aren't mixed.
    """
    vocab = ['type0', 'type1']
    hint1 = {'t': 0, 'p': [{'l': 0, 'r': 1}]}
    hint2 = {'t': 0, 'p': [{'l': 1, 'r': 2}]}
    hint3 = {'t': 1, 'p': [{'l': 2, 'r': 3}]}
    pass_ = StubHintBasedPass(
        {
            'abc': [hint1, hint2, hint3],
        },
        vocabulary=vocab,
    )
    test_case = tmp_path / 'input.txt'
    test_case.write_text('abc')

    state = pass_.new(test_case, tmp_dir=tmp_path)
    all_transforms = collect_all_transforms(pass_, state, test_case)
    assert 'c' in all_transforms  # hint1&2 applied
    assert 'ab' in all_transforms  # hint3 applied
    assert 'b' not in all_transforms  # no attempt to apply different-typed hint1 and hint3
    assert 'a' not in all_transforms  # no attempt to apply different-typed hint2 and hint3

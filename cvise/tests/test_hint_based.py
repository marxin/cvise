from pathlib import Path
from typing import Dict, List, Optional, Sequence

from cvise.passes.hint_based import HintBasedPass
from cvise.tests.testabstract import collect_all_transforms, iterate_pass, validate_hint_bundle
from cvise.utils.hint import Hint, HintBundle, load_hints, Patch
from cvise.utils.process import ProcessEventNotifier


class StubHintBasedPass(HintBasedPass):
    def __init__(self, contents_to_hints: Dict[bytes, Sequence[Hint]], vocabulary: Optional[List[bytes]] = None):
        super().__init__()
        self.contents_to_hints = contents_to_hints
        self.vocabulary = vocabulary or []

    def output_hint_types(self) -> List[bytes]:
        return self.vocabulary

    def generate_hints(self, test_case: Path, *args, **kwargs) -> HintBundle:
        contents = test_case.read_bytes()
        hints = self.contents_to_hints.get(contents, [])
        bundle = HintBundle(vocabulary=self.vocabulary, hints=hints)
        validate_hint_bundle(bundle, test_case, allowed_hint_types=set(self.output_hint_types()))
        return bundle


def test_hint_based_first_char_once(tmp_path: Path):
    """Test the case of a single hint."""
    hint = Hint(patches=[Patch(left=0, right=1)])
    pass_ = StubHintBasedPass(
        {
            b'foo': [hint],
        }
    )
    test_case = tmp_path / 'input.txt'
    test_case.write_text('foo')

    iterate_pass(
        pass_, test_case, tmp_dir=tmp_path, process_event_notifier=ProcessEventNotifier(None), dependee_hints=[]
    )

    assert test_case.read_text() == 'oo'


def test_hint_based_last_char_repeatedly(tmp_path: Path):
    """Test the case of applying a single hint that's different every time."""
    hint_byte0 = Hint(patches=[Patch(left=0, right=1)])
    hint_byte1 = Hint(patches=[Patch(left=1, right=2)])
    hint_byte2 = Hint(patches=[Patch(left=2, right=3)])
    pass_ = StubHintBasedPass(
        {
            b'foo': [hint_byte2],
            b'fo': [hint_byte1],
            b'f': [hint_byte0],
        }
    )
    test_case = tmp_path / 'input.txt'
    test_case.write_text('foo')

    iterate_pass(
        pass_, test_case, tmp_dir=tmp_path, process_event_notifier=ProcessEventNotifier(None), dependee_hints=[]
    )

    assert test_case.read_text() == ''


def test_hint_based_all_chars_grouped(tmp_path: Path):
    """Test the case of multiple hints to be picked up together as a group.

    The logic that chooses ranges of hints to be attempted (the binary search)
    is mostly irrelevant for the test - we only expect it to try *all* hints
    together."""
    hint_byte0 = Hint(patches=[Patch(left=0, right=1)])
    hint_byte1 = Hint(patches=[Patch(left=1, right=2)])
    hint_byte2 = Hint(patches=[Patch(left=2, right=3)])
    pass_ = StubHintBasedPass(
        {
            b'foo': [hint_byte0, hint_byte1, hint_byte2],
        }
    )
    test_case = tmp_path / 'input.txt'
    test_case.write_text('foo')

    iterate_pass(
        pass_, test_case, tmp_dir=tmp_path, process_event_notifier=ProcessEventNotifier(None), dependee_hints=[]
    )

    assert test_case.read_text() == ''


def test_hint_based_state_iteration(tmp_path: Path):
    """Test advancing through multiple hints.

    Unlike iterate_pass-based tests which pretend that any transformation leads
    to a successful interestingness test and proceed immediately, here we
    verify how different hints are attempted."""
    hint_bytes01 = Hint(patches=[Patch(left=0, right=2)])
    hint_bytes12 = Hint(patches=[Patch(left=1, right=3)])
    hint_bytes45 = Hint(patches=[Patch(left=4, right=6)])
    hint_bytes2345 = Hint(patches=[Patch(left=2, right=6)])
    pass_ = StubHintBasedPass(
        {
            b'abc def': [hint_bytes01, hint_bytes12, hint_bytes45, hint_bytes2345],
        }
    )
    test_case = tmp_path / 'input.txt'
    test_case.write_text('abc def')

    state = pass_.new(test_case, tmp_dir=tmp_path, process_event_notifier=ProcessEventNotifier(None), dependee_hints=[])
    all_transforms = collect_all_transforms(pass_, state, test_case)
    assert b'c def' in all_transforms  # 01 applied
    assert b'a def' in all_transforms  # 12 applied
    assert b'abc f' in all_transforms  # 45 applied
    assert b'abf' in all_transforms  # 2345 applied (also 45+2345, with the same result)
    assert b' def' in all_transforms  # 01+12 applied
    assert b'f' in all_transforms  # all hints applied


def test_hint_based_multiple_types(tmp_path: Path):
    """Test advancing through hints of multiple types."""
    vocab = [b'space_removal', b'b_removal']
    hint_space1 = Hint(type=0, patches=[Patch(left=3, right=4)])
    hint_space2 = Hint(type=0, patches=[Patch(left=7, right=8)])
    hint_b1 = Hint(type=1, patches=[Patch(left=1, right=2)])
    hint_b2 = Hint(type=1, patches=[Patch(left=6, right=7)])
    pass_ = StubHintBasedPass(
        {
            b'aba cab a': [hint_b1, hint_space1, hint_b2, hint_space2],
        },
        vocabulary=vocab,
    )
    test_case = tmp_path / 'input.txt'
    test_case.write_text('aba cab a')

    state = pass_.new(test_case, tmp_dir=tmp_path, process_event_notifier=ProcessEventNotifier(None), dependee_hints=[])
    all_transforms = collect_all_transforms(pass_, state, test_case)
    assert b'abacab a' in all_transforms  # space1 applied
    assert b'aba caba' in all_transforms  # space2 applied
    assert b'abacaba' in all_transforms  # space1&2 applied
    assert b'aa cab a' in all_transforms  # hint_b1 applied
    assert b'aba ca a' in all_transforms  # hint_b2 applied
    assert b'aa ca a' in all_transforms  # hint_b1&2 applied


def test_hint_based_type1_fewer_than_type2(tmp_path: Path):
    """Test the scenario there are two hint types, with fewer hints for the first type.

    Verify that subranges of same-typed hints are checked, but differently-typed hints aren't mixed.
    """
    vocab = [b'type0', b'type1']
    hint1 = Hint(type=0, patches=[Patch(left=0, right=1)])
    hint2 = Hint(type=1, patches=[Patch(left=1, right=2)])
    hint3 = Hint(type=1, patches=[Patch(left=2, right=3)])
    pass_ = StubHintBasedPass(
        {
            b'abc': [hint1, hint2, hint3],
        },
        vocabulary=vocab,
    )
    test_case = tmp_path / 'input.txt'
    test_case.write_text('abc')

    state = pass_.new(test_case, tmp_dir=tmp_path, process_event_notifier=ProcessEventNotifier(None), dependee_hints=[])
    all_transforms = collect_all_transforms(pass_, state, test_case)
    assert b'bc' in all_transforms  # hint1 applied
    assert b'a' in all_transforms  # hint2&3 applied
    assert b'c' not in all_transforms  # no attempt to apply different-typed hint1 and hint2
    assert b'b' not in all_transforms  # no attempt to apply different-typed hint1 and hint3


def test_hint_based_type2_fewer_than_type1(tmp_path: Path):
    """Test the scenario there are two hint types, with fewer hints for the second type.

    Verify that subranges of same-typed hints are checked, but differently-typed hints aren't mixed.
    """
    vocab = [b'type0', b'type1']
    hint1 = Hint(type=0, patches=[Patch(left=0, right=1)])
    hint2 = Hint(type=0, patches=[Patch(left=1, right=2)])
    hint3 = Hint(type=1, patches=[Patch(left=2, right=3)])
    pass_ = StubHintBasedPass(
        {
            b'abc': [hint1, hint2, hint3],
        },
        vocabulary=vocab,
    )
    test_case = tmp_path / 'input.txt'
    test_case.write_text('abc')

    state = pass_.new(test_case, tmp_dir=tmp_path, process_event_notifier=ProcessEventNotifier(None), dependee_hints=[])
    all_transforms = collect_all_transforms(pass_, state, test_case)
    assert b'c' in all_transforms  # hint1&2 applied
    assert b'ab' in all_transforms  # hint3 applied
    assert b'b' not in all_transforms  # no attempt to apply different-typed hint1 and hint3
    assert b'a' not in all_transforms  # no attempt to apply different-typed hint2 and hint3


def test_hint_based_non_utf8(tmp_path: Path):
    """Test the case of non UTF-8 inputs."""
    input = b'f\0o\xffo\xc3\x84'
    hint12 = Hint(patches=[Patch(left=1, right=2)])
    hint23 = Hint(patches=[Patch(left=2, right=3)])
    hint34 = Hint(patches=[Patch(left=3, right=4)])
    hint57 = Hint(patches=[Patch(left=5, right=7)])
    pass_ = StubHintBasedPass(
        {
            input: [hint12, hint23, hint34, hint57],
        }
    )
    test_case = tmp_path / 'input.txt'
    test_case.write_bytes(input)

    state = pass_.new(test_case, tmp_dir=tmp_path, process_event_notifier=ProcessEventNotifier(None), dependee_hints=[])
    all_transforms = collect_all_transforms(pass_, state, test_case)
    assert b'fo\xffo\xc3\x84' in all_transforms  # hint12 applied
    assert b'f\0\xffo\xc3\x84' in all_transforms  # hint23 applied
    assert b'f\0oo\xc3\x84' in all_transforms  # hint34 applied
    assert b'f\0o\xffo' in all_transforms  # hint57 applied
    assert b'fo' in all_transforms  # all applied


def test_hint_based_special_hints_not_attempted(tmp_path: Path):
    """Test that special hints (whose type starts from "@") aren't attempted in the pass transform() calls."""
    input = b'foo'
    test_case = tmp_path / 'input.txt'
    vocab = [b'sometype', b'@specialtype']
    hint_regular = Hint(type=0, patches=[Patch(left=0, right=1)])
    hint_special = Hint(type=1, patches=[Patch(left=1, right=2)])
    pass_ = StubHintBasedPass(
        {
            input: [hint_regular, hint_special],
        },
        vocabulary=vocab,
    )
    test_case.write_bytes(input)

    state = pass_.new(test_case, tmp_dir=tmp_path, process_event_notifier=ProcessEventNotifier(None), dependee_hints=[])
    all_transforms = collect_all_transforms(pass_, state, test_case)
    assert b'oo' in all_transforms  # hint_regular applied
    assert b'fo' not in all_transforms  # hint_special not applied


def test_hint_based_special_hints_stored(tmp_path: Path):
    """Test that special hints produced by a pass are stored on disk, even if no other hints are produced."""
    input = b'foo'
    test_case = tmp_path / 'input.txt'
    hint_type = b'@specialtype'
    hint = Hint(type=0, patches=[Patch(left=1, right=2)])
    pass_ = StubHintBasedPass(
        {
            input: [hint],
        },
        vocabulary=[hint_type],
    )
    test_case.write_bytes(input)

    state = pass_.new(test_case, tmp_dir=tmp_path, process_event_notifier=ProcessEventNotifier(None), dependee_hints=[])
    assert state is not None
    bundle_paths = state.hint_bundle_paths()
    assert len(bundle_paths) == 1
    assert hint_type in bundle_paths
    bundle = load_hints(bundle_paths[hint_type], begin_index=None, end_index=None)
    assert bundle.hints == [hint]

    all_transforms = collect_all_transforms(pass_, state, test_case)
    assert all_transforms == set()
    assert pass_.advance(test_case, state) is None

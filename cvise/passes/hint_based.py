from __future__ import annotations
from pathlib import Path
from typing import Union

from cvise.passes.abstract import AbstractPass, BinaryState, PassResult
from cvise.utils.hint import apply_hints, HintBundle, load_hints, store_hints

HINTS_FILE_NAME = 'hints.jsonl.zst'


class HintState:
    def __init__(self, hint_count: int, hints_file_path: Path, binary_state: BinaryState):
        assert hint_count > 0
        self.hint_count = hint_count
        self.hints_file_path = hints_file_path
        self.binary_state = binary_state

    @staticmethod
    def create(hint_count: int, hints_file_path: Path) -> HintState:
        binary_state = BinaryState.create(hint_count)
        return HintState(hint_count, hints_file_path, binary_state)

    def advance(self) -> Union[HintState, None]:
        next_state = self.binary_state.advance()
        if next_state is None:
            return None
        return HintState(self.hint_count, self.hints_file_path, next_state)

    def advance_on_success(self, new_hint_count) -> Union[HintState, None]:
        next_state = self.binary_state.advance_on_success(new_hint_count)
        if next_state is None:
            return None
        return HintState(new_hint_count, self.hints_file_path, next_state)


class HintBasedPass(AbstractPass):
    """Base class for hint-based passes.

    Provides default implementations of new/transform/advance operations, which only require the subclass to implement
    the generate_hints() method."""

    def generate_hints(self, test_case: Path) -> HintBundle:
        raise NotImplementedError(f"Class {type(self).__name__} has not implemented 'generate_hints'!")

    def new(self, test_case, tmp_dir, **kwargs):
        hints = self.generate_hints(test_case)
        return self.new_from_hints(hints, tmp_dir)

    def transform(self, test_case, state, process_event_notifier):
        hints_range_begin = state.binary_state.index
        hints_range_end = state.binary_state.end()
        hints = load_hints(state.hints_file_path, hints_range_begin, hints_range_end)
        new_data = apply_hints(hints, Path(test_case))
        Path(test_case).write_text(new_data)
        return (PassResult.OK, state)

    def advance(self, test_case, state):
        return state.advance()

    def advance_on_success(self, test_case, state):
        hints = self.generate_hints(test_case)
        return self.advance_on_success_from_hints(hints, state)

    def new_from_hints(self, bundle: HintBundle, tmp_dir: str) -> Union[HintState, None]:
        """Creates a state for pre-generated hints.

        Can be used by subclasses which don't follow the typical approach with implementing generate_hints()."""
        if not bundle.hints:
            return None
        hints_file_path = tmp_dir / HINTS_FILE_NAME
        store_hints(bundle, hints_file_path)
        return HintState.create(len(bundle.hints), hints_file_path)

    def advance_on_success_from_hints(self, bundle: HintBundle, state: HintState) -> Union[HintState, None]:
        """Advances the state after a successful reduction, given pre-generated hints.

        Can be used by subclasses which don't follow the typical approach with implementing generate_hints()."""
        if not bundle.hints:
            return None
        store_hints(bundle, state.hints_file_path)
        return state.advance_on_success(len(bundle.hints))

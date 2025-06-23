from __future__ import annotations
from abc import ABCMeta, abstractmethod
from pathlib import Path
from typing import Sequence, Union

from cvise.passes.abstract import AbstractPass, BinaryState, PassResult
from cvise.utils.hint import apply_hints, load_hints, store_hints

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


class HintBasedPass(AbstractPass, metaclass=ABCMeta):
    """Based class for hint-based passes.

    Subclasses must implement the generate_hints() method; the
    new/transform/advance operations are taken care by the generic logic here.
    """

    @abstractmethod
    def generate_hints(self, test_case: Path) -> Sequence[object]:
        pass

    def new(self, test_case, temp_dir, **kwargs):
        hints = self.generate_hints(test_case)
        if not hints:
            return None
        hints_file_path = temp_dir / HINTS_FILE_NAME
        store_hints(hints, hints_file_path)
        return HintState.create(len(hints), hints_file_path)

    def transform(self, test_case, state, process_event_notifier):
        hints = load_hints(state.hints_file_path, state.binary_state.index, state.binary_state.end())
        apply_hints(hints, Path(test_case))
        return (PassResult.OK, state)

    def advance(self, test_case, state):
        return state.advance()

    def advance_on_success(self, test_case, state):
        hints = self.generate_hints(test_case)
        if not hints:
            return None
        store_hints(hints, state.hints_file_path)
        return state.advance_on_success(len(hints))

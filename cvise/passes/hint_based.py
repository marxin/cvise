from __future__ import annotations
from copy import copy
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Union

from cvise.passes.abstract import AbstractPass, BinaryState, PassResult
from cvise.utils.hint import apply_hints, group_hints_by_type, HintBundle, HintApplicationStats, load_hints, store_hints

HINTS_FILE_NAME_TEMPLATE = 'hints{type}.jsonl.zst'


@dataclass
class PerTypeHintState:
    """A sub-item of HintState storing information for a particular hint type.

    See the comment in the HintBasedPass.
    """

    # A hint type for which this state is for; an empty string if a hint doesn't explicitly specify types.
    type: str
    # Only the base name, not a full path - it's a small optimization (and we anyway need to store the tmp dir in the
    # HintState).
    hints_file_name: Path
    # State of the enumeration over hints with this particular type.
    underlying_state: Any

    def advance(self) -> Union[PerTypeHintState, None]:
        # Move to the next step in the enumeration, or to None if this was the last step.
        next = self.underlying_state.advance()
        if next is None:
            return None
        new = copy(self)
        new.underlying_state = next
        return new

    def advance_on_success(self, new_hint_count: int) -> Union[PerTypeHintState, None]:
        next = self.underlying_state.advance_on_success(new_hint_count)
        if next is None:
            return None
        new = copy(self)
        new.underlying_state = next
        return new


class HintState:
    """Stores the current state of the HintBasedPass.

    Conceptually, it's representing multiple enumerations (by default - binary searches), one for each hint type. These
    are applied & advanced in a round-robin fashion. See the comment in the HintBasedPass.
    """

    def __init__(self, tmp_dir: Path, per_type_states: List[PerTypeHintState]):
        self.tmp_dir = tmp_dir
        # Sort the per-type states to have deterministic and repeatable enumeration order.
        self.per_type_states = sorted(per_type_states, key=lambda s: s.type if s else '')
        # Pointer to the current per-type state in the round-robin enumeration.
        self.ptr = 0

    def __repr__(self):
        parts = []
        for i, s in enumerate(self.per_type_states):
            mark = '[*]' if i == self.ptr and len(self.per_type_states) > 1 else ''
            type_s = s.type + ': ' if s.type else ''
            parts.append(f'{mark}{type_s}{s.underlying_state.compact_repr()}')
        return f'HintState({", ".join(parts)})'

    def advance(self) -> Union[HintState, None]:
        # First, prepare the current type's sub-state to point to the next enumeration step.
        new_substate = self.per_type_states[self.ptr].advance()
        if new_substate is None and len(self.per_type_states) == 1:
            # The last type's enumeration finished - nothing to be done more.
            return None

        # Second, create the result with just this sub-state updated/deleted.
        new = HintState(self.tmp_dir, copy(self.per_type_states))
        if new_substate is None:
            del new.per_type_states[self.ptr]
        else:
            new.per_type_states[self.ptr] = new_substate

        # Third, set the result's pointer to the next sub-state after the updated/deleted one, in the round-robin
        # fashion.
        new.ptr = self.ptr
        if new_substate is not None:
            new.ptr += 1
        new.ptr %= len(new.per_type_states)
        return new

    def advance_on_success(self, type_to_bundle: Dict[str, HintBundle]):
        sub_states = []
        # Advance all previously present hint types' substates. We ignore any newly appearing hint types because it's
        # nontrivial to distinguish geniunely new hints from those that we (unsuccessfully) checked.
        for old_substate in self.per_type_states:
            if old_substate.type not in type_to_bundle:
                # This hint type disappeared - probably all candidates have been removed by the reduction.
                continue
            new_hint_count = len(type_to_bundle[old_substate.type].hints)
            new_substate = old_substate.advance_on_success(new_hint_count)
            if new_substate:
                sub_states.append(new_substate)
        if not sub_states:
            return None
        return HintState(self.tmp_dir, sub_states)


class HintBasedPass(AbstractPass):
    """Base class for hint-based passes.

    Provides default implementations of new/transform/advance operations, which only require the subclass to implement
    the generate_hints() method.

    Takes care of managing multiple enumerations, one per each hint type. By default, the enumeration is performed via
    the binary search. For example, if the pass generated 10 hints of "comment" type and 40 hints of "function" type,
    the order of enumeration in this pass' jobs would be:
    * transform #1: attempt applying [0..10) "comment" hints;
    * transform #2: attempt applying [0..40) "function" hints;
    * transform #3: attempt applying [0..5) "comment" hints;
    * transform #4: attempt applying [0..20) "function" hints;
    * transform #5: attempt applying [5..10) "comment" hints;
    * etc.
    """

    def generate_hints(self, test_case: Path) -> HintBundle:
        raise NotImplementedError(f"Class {type(self).__name__} has not implemented 'generate_hints'!")

    def create_elementary_state(self, hint_count: int) -> Any:
        """Creates a single underlying state for enumerating hints of a particular type.

        Intended to be overridden by subclasses that don't want the default behavior (binary search).
        """
        return BinaryState.create(instances=hint_count)

    def new(self, test_case, tmp_dir, *args, **kwargs):
        hints = self.generate_hints(test_case)
        return self.new_from_hints(hints, tmp_dir)

    def transform(self, test_case, state: HintState, *args, **kwargs):
        self.load_and_apply_hints(test_case, [state])
        return PassResult.OK, state

    @staticmethod
    def load_and_apply_hints(test_case: Path, states: List[HintState]) -> HintApplicationStats:
        hint_bundles: List[HintBundle] = []
        for state in states:
            sub_state = state.per_type_states[state.ptr]
            hints_range_begin = sub_state.underlying_state.index
            hints_range_end = sub_state.underlying_state.end()
            hint_bundles.append(
                load_hints(state.tmp_dir / sub_state.hints_file_name, hints_range_begin, hints_range_end)
            )
        new_data, stats = apply_hints(hint_bundles, test_case)
        Path(test_case).write_bytes(new_data)
        return stats

    def advance(self, test_case, state):
        return state.advance()

    def advance_on_success(self, test_case, state, *args, **kwargs):
        hints = self.generate_hints(test_case)
        return self.advance_on_success_from_hints(hints, state)

    def new_from_hints(self, bundle: HintBundle, tmp_dir: Path) -> Union[HintState, None]:
        """Creates a state for pre-generated hints.

        Can be used by subclasses which don't follow the typical approach with implementing generate_hints()."""
        if not bundle.hints:
            return None
        type_to_bundle = group_hints_by_type(bundle)
        self.backfill_pass_names(type_to_bundle)
        type_to_file_name = store_hints_per_type(tmp_dir, type_to_bundle)
        sub_states = []
        # Initialize a separate enumeration for each group of hints sharing a particular type.
        for type, sub_bundle in type_to_bundle.items():
            underlying = self.create_elementary_state(len(sub_bundle.hints))
            sub_states.append(
                PerTypeHintState(type=type, hints_file_name=type_to_file_name[type], underlying_state=underlying)
            )
        return HintState(tmp_dir, sub_states)

    def advance_on_success_from_hints(self, bundle: HintBundle, state: HintState) -> Union[HintState, None]:
        """Advances the state after a successful reduction, given pre-generated hints.

        Can be used by subclasses which don't follow the typical approach with implementing generate_hints()."""
        if not bundle.hints:
            return None
        type_to_bundle = group_hints_by_type(bundle)
        self.backfill_pass_names(type_to_bundle)
        store_hints_per_type(state.tmp_dir, type_to_bundle)
        return state.advance_on_success(type_to_bundle)

    def backfill_pass_names(self, type_to_bundle: Dict[str, HintBundle]) -> None:
        for bundle in type_to_bundle.values():
            if not bundle.pass_name:
                bundle.pass_name = repr(self)


def store_hints_per_type(tmp_dir: Path, type_to_bundle: Dict[str, HintBundle]) -> Dict[str, Path]:
    type_to_file_name = {}
    for type, sub_bundle in type_to_bundle.items():
        file_name = Path(HINTS_FILE_NAME_TEMPLATE.format(type=type))
        store_hints(sub_bundle, tmp_dir / file_name)
        type_to_file_name[type] = file_name
    return type_to_file_name

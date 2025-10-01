from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Sequence, Tuple, Union

from cvise.passes.abstract import AbstractPass, BinaryState, PassResult, ProcessEventNotifier
from cvise.utils.hint import (
    apply_hints,
    group_hints_by_type,
    is_special_hint_type,
    HintBundle,
    HintApplicationStats,
    load_hints,
    store_hints,
)

HINTS_FILE_NAME_TEMPLATE = 'hints{type}.jsonl.zst'


@dataclass(frozen=True)
class PerTypeHintState:
    """A sub-item of HintState storing information for a particular hint type.

    See the comment in the HintBasedPass.
    """

    # A hint type for which this state is for; an empty string if a hint doesn't explicitly specify types.
    type: bytes
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
        return PerTypeHintState(
            type=self.type,
            hints_file_name=self.hints_file_name,
            underlying_state=next,
        )

    def advance_on_success(self, new_hint_count: int) -> Union[PerTypeHintState, None]:
        next = self.underlying_state.advance_on_success(new_hint_count)
        if next is None:
            return None
        return PerTypeHintState(
            type=self.type,
            hints_file_name=self.hints_file_name,
            underlying_state=next,
        )


@dataclass(frozen=True)
class SpecialHintState:
    """A sub-item of HintState for "special" hint types - those that start from "@".

    Such hints aren't attempted as reduction attempts themselves, instead they convey information from one pass to
    another - hence there's no underlying_state here.
    """

    type: bytes
    hints_file_name: Path
    hint_count: int


@dataclass(frozen=True)
class HintState:
    """Stores the current state of the HintBasedPass.

    Conceptually, it's representing multiple enumerations (by default - binary searches), one for each hint type. These
    are applied & advanced in a round-robin fashion. See the comment in the HintBasedPass.
    """

    tmp_dir: Path
    # The enumeration state for each hint type. Sorted by type (in order to have deterministic and repeatable
    # enumeration order).
    per_type_states: Tuple[PerTypeHintState, ...]
    # Pointer to the current per-type state in the round-robin enumeration.
    ptr: int
    # Information for "special" hint types (those that start with "@"). They're stored separately because we don't
    # attempt applying them during enumeration - they're only intended as inputs for other passes that depend on them.
    special_hints: Tuple[SpecialHintState, ...]

    @staticmethod
    def create(tmp_dir: Path, per_type_states: List[PerTypeHintState], special_hints: List[SpecialHintState]):
        sorted_states = sorted(per_type_states, key=lambda s: s.type)
        sorted_special_hints = sorted(special_hints, key=lambda s: s.type)
        return HintState(
            tmp_dir=tmp_dir, per_type_states=tuple(sorted_states), ptr=0, special_hints=tuple(sorted_special_hints)
        )

    def __repr__(self):
        parts = []
        for i, s in enumerate(self.per_type_states):
            mark = '[*]' if i == self.ptr and len(self.per_type_states) > 1 else ''
            type_s = s.type.decode() + ': ' if s.type else ''
            parts.append(f'{mark}{type_s}{s.underlying_state.compact_repr()}')
        for s in self.special_hints:
            parts.append(f'{s.type.decode()}: {s.hint_count}')
        return f'HintState({", ".join(parts)})'

    def real_chunk(self) -> int:
        return self.per_type_states[self.ptr].underlying_state.real_chunk()

    def advance(self) -> Union[HintState, None]:
        if not self.per_type_states:
            # This is reachable if only special hint types are present.
            return None

        # First, prepare the current type's sub-state to point to the next enumeration step.
        new_substate = self.per_type_states[self.ptr].advance()
        if new_substate is None and len(self.per_type_states) == 1:
            # The last type's enumeration finished - nothing to be done more.
            return None

        # Second, create the result with just this sub-state updated/deleted.
        new_per_type_states = list(self.per_type_states)
        if new_substate is None:
            del new_per_type_states[self.ptr]
        else:
            new_per_type_states[self.ptr] = new_substate

        # Third, set the result's pointer to the next sub-state after the updated/deleted one, in the round-robin
        # fashion.
        new_ptr = self.ptr
        if new_substate is not None:
            new_ptr += 1
        new_ptr %= len(new_per_type_states)

        return HintState(
            tmp_dir=self.tmp_dir,
            per_type_states=tuple(new_per_type_states),
            ptr=new_ptr,
            special_hints=self.special_hints,
        )

    def advance_on_success(self, type_to_bundle: Dict[bytes, HintBundle]):
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
        return HintState(
            tmp_dir=self.tmp_dir, per_type_states=tuple(sub_states), ptr=0, special_hints=self.special_hints
        )

    def hint_bundle_paths(self) -> Dict[bytes, Path]:
        return {
            substate.type: self.tmp_dir / substate.hints_file_name
            for substate in self.per_type_states + self.special_hints
        }


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

    def generate_hints(
        self,
        test_case: Path,
        process_event_notifier: ProcessEventNotifier,
        dependee_hints: List[HintBundle],
        *args,
        **kwargs,
    ) -> HintBundle:
        raise NotImplementedError(f"Class {type(self).__name__} has not implemented 'generate_hints'!")

    def input_hint_types(self) -> List[bytes]:
        """Declares hint types that are consumed by this pass as inputs.

        Intended to be overridden by subclasses, in cases where dependencies between passes need to be implemented:
        e.g., if a pass wants to consume hints of type "foo-hint-type" produced by some PassA and PassB.

        Each returned hint type must be declared as an output of at least one other pass. Cycles aren't allowed.
        """
        return []

    def output_hint_types(self) -> List[bytes]:
        """Declares hint types that are produced by this pass.

        A pass must override this method if it produces hints with a nonempty type (the "t" field).
        """
        return []

    def create_elementary_state(self, hint_count: int) -> Any:
        """Creates a single underlying state for enumerating hints of a particular type.

        Intended to be overridden by subclasses that don't want the default behavior (binary search).
        """
        return BinaryState.create(instances=hint_count)

    def new(
        self,
        test_case: Path,
        tmp_dir: Path,
        process_event_notifier: ProcessEventNotifier,
        dependee_hints: List[HintBundle],
        *args,
        **kwargs,
    ):
        hints = self.generate_hints(
            test_case, process_event_notifier=process_event_notifier, dependee_hints=dependee_hints
        )
        return self.new_from_hints(hints, tmp_dir)

    def transform(self, test_case: Path, state: HintState, original_test_case: Path, *args, **kwargs):
        if not state.per_type_states:  # possible if all hints produced by new() were "special"
            return PassResult.STOP, state
        self.load_and_apply_hints(original_test_case, test_case, [state])
        return PassResult.OK, state

    @staticmethod
    def load_and_apply_hints(
        original_test_case: Path, test_case: Path, states: Sequence[HintState]
    ) -> HintApplicationStats:
        hint_bundles: List[HintBundle] = []
        for state in states:
            sub_state = state.per_type_states[state.ptr]
            hints_range_begin = sub_state.underlying_state.index
            hints_range_end = sub_state.underlying_state.end()
            hint_bundles.append(
                load_hints(state.tmp_dir / sub_state.hints_file_name, hints_range_begin, hints_range_end)
            )
        stats = apply_hints(hint_bundles, source_path=original_test_case, destination_path=test_case)
        return stats

    def advance(self, test_case: Path, state):
        return state.advance()

    def advance_on_success(
        self,
        test_case: Path,
        state,
        process_event_notifier: ProcessEventNotifier,
        dependee_hints: List[HintBundle],
        *args,
        **kwargs,
    ):
        hints = self.generate_hints(
            test_case, process_event_notifier=process_event_notifier, dependee_hints=dependee_hints
        )
        return self.advance_on_success_from_hints(hints, state)

    def new_from_hints(self, bundle: HintBundle, tmp_dir: Path) -> Union[HintState, None]:
        """Creates a state for pre-generated hints.

        Can be used by subclasses which don't follow the typical approach with implementing generate_hints()."""
        if not bundle.hints:
            return None
        type_to_bundle = group_hints_by_type(bundle)
        self.backfill_pass_names(type_to_bundle)
        type_to_file_name = store_hints_per_type(tmp_dir, type_to_bundle)
        sub_states: List[PerTypeHintState] = []
        special_states: List[SpecialHintState] = []
        for type, sub_bundle in type_to_bundle.items():
            sub_bundle.hints.sort()
            if is_special_hint_type(type):
                # "Special" hints aren't attempted in transform() jobs - only store them to be consumed by other passes.
                special_states.append(
                    SpecialHintState(
                        type=type, hints_file_name=type_to_file_name[type], hint_count=len(sub_bundle.hints)
                    )
                )
            else:
                # Initialize a separate enumeration for this group of hints sharing a particular type.
                underlying = self.create_elementary_state(len(sub_bundle.hints))
                if underlying is None:
                    continue
                sub_states.append(
                    PerTypeHintState(type=type, hints_file_name=type_to_file_name[type], underlying_state=underlying)
                )
        if not sub_states and not special_states:
            return None
        return HintState.create(tmp_dir, sub_states, special_states)

    def advance_on_success_from_hints(self, bundle: HintBundle, state: HintState) -> Union[HintState, None]:
        """Advances the state after a successful reduction, given pre-generated hints.

        Can be used by subclasses which don't follow the typical approach with implementing generate_hints()."""
        if not bundle.hints:
            return None
        type_to_bundle = group_hints_by_type(bundle)
        for sub_bundle in type_to_bundle.values():
            sub_bundle.hints.sort()
        self.backfill_pass_names(type_to_bundle)
        store_hints_per_type(state.tmp_dir, type_to_bundle)
        return state.advance_on_success(type_to_bundle)

    def backfill_pass_names(self, type_to_bundle: Dict[bytes, HintBundle]) -> None:
        for bundle in type_to_bundle.values():
            if not bundle.pass_name:
                bundle.pass_name = repr(self)


def store_hints_per_type(tmp_dir: Path, type_to_bundle: Dict[bytes, HintBundle]) -> Dict[bytes, Path]:
    type_to_file_name = {}
    for type, sub_bundle in type_to_bundle.items():
        file_name = Path(HINTS_FILE_NAME_TEMPLATE.format(type=type.decode()))
        store_hints(sub_bundle, tmp_dir / file_name)
        type_to_file_name[type] = file_name
    return type_to_file_name

from __future__ import annotations
from collections.abc import Sequence
from dataclasses import dataclass
import os
from pathlib import Path
import tempfile
from typing import Any

from cvise.passes.abstract import AbstractPass, BinaryState, PassResult, ProcessEventNotifier
from cvise.utils.fileutil import sanitize_for_file_name
from cvise.utils.hint import (
    apply_hints,
    group_hints_by_type,
    is_special_hint_type,
    HintBundle,
    HintApplicationStats,
    load_hints,
    sort_hints,
    store_hints,
)

_HINTS_FILE_NAME_PREFIX_TEMPLATE = 'hints{type}-'
_HINTS_FILE_NAME_SUFFIX = '.jsonl.zst'


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

    def __repr__(self):
        type_s = self.type.decode() + ': ' if self.type else ''
        return f'PerTypeHintState({type_s}{self.underlying_state.compact_repr()})'

    def advance(self) -> PerTypeHintState | None:
        # Move to the next step in the enumeration, or to None if this was the last step.
        next = self.underlying_state.advance()
        if next is None:
            return None
        return PerTypeHintState(
            type=self.type,
            hints_file_name=self.hints_file_name,
            underlying_state=next,
        )

    def advance_on_success(self, new_hint_count: int, new_file_name: Path) -> PerTypeHintState | None:
        next = self.underlying_state.advance_on_success(new_hint_count)
        if next is None:
            return None
        return PerTypeHintState(
            type=self.type,
            hints_file_name=new_file_name,
            underlying_state=next,
        )

    def subset_of(self, other: PerTypeHintState) -> bool:
        if (
            self.type != other.type
            or self.hints_file_name != other.hints_file_name
            or not isinstance(self.underlying_state, BinaryState)
            or not isinstance(other.underlying_state, BinaryState)
            or self.underlying_state.instances != other.underlying_state.instances
        ):
            return False
        return (
            other.underlying_state.index <= self.underlying_state.index
            and self.underlying_state.end() <= other.underlying_state.end()
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
    per_type_states: tuple[PerTypeHintState, ...]
    # Pointer to the current per-type state in the round-robin enumeration.
    ptr: int
    # Information for "special" hint types (those that start with "@"). They're stored separately because we don't
    # attempt applying them during enumeration - they're only intended as inputs for other passes that depend on them.
    special_hints: tuple[SpecialHintState, ...]

    @staticmethod
    def create(tmp_dir: Path, per_type_states: list[PerTypeHintState], special_hints: list[SpecialHintState]):
        assert per_type_states or special_hints
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

    def current_substate(self) -> PerTypeHintState:
        return self.per_type_states[self.ptr]

    def real_chunk(self) -> int:
        return self.current_substate().underlying_state.real_chunk()

    def advance(self) -> HintState | None:
        if not self.per_type_states:
            # This is reachable if only special hint types are present.
            return None

        # First, prepare the current type's sub-state to point to the next enumeration step.
        new_substate = self.current_substate().advance()
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

    def advance_on_success(
        self, type_to_bundle: dict[bytes, HintBundle], type_to_file_name: dict[bytes, Path], new_tmp_dir: Path
    ) -> HintState | None:
        # Advance all previously present hint types' substates. We ignore any newly appearing hint types because it's
        # nontrivial to distinguish geniunely new hints from those that we (unsuccessfully) checked.
        sub_states = []
        for old_substate in self.per_type_states:
            type = old_substate.type
            if type not in type_to_bundle:
                # This hint type disappeared - probably all candidates have been removed by the reduction.
                continue
            new_hint_count = len(type_to_bundle[type].hints)
            new_substate = old_substate.advance_on_success(new_hint_count, type_to_file_name[type])
            if new_substate:
                sub_states.append(new_substate)

        new_special_hints = [
            SpecialHintState(type=type, hints_file_name=file_name, hint_count=len(type_to_bundle[type].hints))
            for type, file_name in type_to_file_name.items()
            if is_special_hint_type(type)
        ]
        new_special_hints.sort(key=lambda s: s.type)

        if not sub_states and not new_special_hints:
            return None
        return HintState(
            tmp_dir=new_tmp_dir, per_type_states=tuple(sub_states), ptr=0, special_hints=tuple(new_special_hints)
        )

    def subset_of(self, other: HintState) -> bool:
        if not self.per_type_states or not other.per_type_states:
            return False
        return self.current_substate().subset_of(other.current_substate())

    def hint_bundle_paths(self) -> dict[bytes, Path]:
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
        dependee_hints: list[HintBundle],
        *args,
        **kwargs,
    ) -> HintBundle:
        raise NotImplementedError(f"Class {type(self).__name__} has not implemented 'generate_hints'!")

    def input_hint_types(self) -> list[bytes]:
        """Declares hint types that are consumed by this pass as inputs.

        Intended to be overridden by subclasses, in cases where dependencies between passes need to be implemented:
        e.g., if a pass wants to consume hints of type "foo-hint-type" produced by some PassA and PassB.

        Each returned hint type must be declared as an output of at least one other pass. Cycles aren't allowed.
        """
        return []

    def output_hint_types(self) -> list[bytes]:
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
        dependee_hints: list[HintBundle],
        *args,
        **kwargs,
    ):
        hints = self.generate_hints(
            test_case, process_event_notifier=process_event_notifier, dependee_hints=dependee_hints
        )
        return self.new_from_hints(hints, tmp_dir)

    def transform(self, test_case: Path, state: HintState, original_test_case: Path, *args, **kwargs):
        if not state.per_type_states:  # possible if all hints produced by new()/advance_on_success() were "special"
            return PassResult.STOP, None
        self.load_and_apply_hints(original_test_case, test_case, [state])
        return PassResult.OK, state

    @staticmethod
    def load_and_apply_hints(
        original_test_case: Path, test_case: Path, states: Sequence[HintState]
    ) -> HintApplicationStats:
        hint_bundles: list[HintBundle] = []
        for state in states:
            sub_state = state.current_substate()
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
        new_tmp_dir: Path,
        process_event_notifier: ProcessEventNotifier,
        dependee_hints: list[HintBundle],
        *args,
        **kwargs,
    ):
        hints = self.generate_hints(
            test_case, process_event_notifier=process_event_notifier, dependee_hints=dependee_hints
        )
        return self.advance_on_success_from_hints(hints, state, new_tmp_dir)

    def new_from_hints(self, bundle: HintBundle, tmp_dir: Path) -> HintState | None:
        """Creates a state for pre-generated hints.

        Can be used by subclasses which don't follow the typical approach with implementing generate_hints()."""
        if not bundle.hints:
            return None
        type_to_bundle = group_hints_by_type(bundle)
        self.backfill_pass_names(type_to_bundle)
        for sub_bundle in type_to_bundle.values():
            sort_hints(sub_bundle)
        type_to_file_name = _store_hints_per_type(tmp_dir, type_to_bundle)
        sub_states: list[PerTypeHintState] = []
        special_states: list[SpecialHintState] = []
        for type, sub_bundle in type_to_bundle.items():
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

    def advance_on_success_from_hints(
        self, bundle: HintBundle, state: HintState, new_tmp_dir: Path
    ) -> HintState | None:
        """Advances the state after a successful reduction, given pre-generated hints.

        Can be used by subclasses which don't follow the typical approach with implementing generate_hints()."""
        if not bundle.hints:
            return None
        type_to_bundle = group_hints_by_type(bundle)
        for sub_bundle in type_to_bundle.values():
            sort_hints(sub_bundle)
        self.backfill_pass_names(type_to_bundle)
        type_to_file_name = _store_hints_per_type(new_tmp_dir, type_to_bundle)
        return state.advance_on_success(type_to_bundle, type_to_file_name, new_tmp_dir)

    def backfill_pass_names(self, type_to_bundle: dict[bytes, HintBundle]) -> None:
        for bundle in type_to_bundle.values():
            if not bundle.pass_name:
                bundle.pass_name = repr(self)
            if not bundle.pass_user_visible_name:
                bundle.pass_user_visible_name = self.user_visible_name()


def _store_hints_per_type(tmp_dir: Path, type_to_bundle: dict[bytes, HintBundle]) -> dict[bytes, Path]:
    type_to_file_name = {}
    for type, sub_bundle in type_to_bundle.items():
        path = _create_file_with_unique_name(tmp_dir, type)
        store_hints(sub_bundle, path)
        type_to_file_name[type] = path.relative_to(tmp_dir)
    return type_to_file_name


def _create_file_with_unique_name(tmp_dir: Path, hint_type: bytes) -> Path:
    type_sanitized = sanitize_for_file_name(hint_type.decode())
    prefix = _HINTS_FILE_NAME_PREFIX_TEMPLATE.format(type=type_sanitized)
    handle, path = tempfile.mkstemp(dir=tmp_dir, prefix=prefix, suffix=_HINTS_FILE_NAME_SUFFIX)
    os.close(handle)
    return Path(path)

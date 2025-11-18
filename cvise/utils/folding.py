"""Implementation of folding (merging) multiple successful transformations."""

import random
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from cvise.passes.abstract import PassResult
from cvise.passes.hint_based import HintBasedPass, HintState


@dataclass(frozen=True, slots=True)
class FoldingStateIn:
    """Input parameters for a folding job's transform."""

    sub_states: tuple[HintState, ...]

    def real_chunk(self) -> int:
        return sum(s.real_chunk() for s in self.sub_states)


@dataclass(frozen=True, slots=True)
class FoldingStateOut(FoldingStateIn):
    """Results returned from a folding job's transform."""

    size_delta_per_pass: dict[str, int]
    passes_ordered_by_delta: list[str]


class FoldingManager:
    """Implements logic for folding (merging) multiple successful transformations.

    The idea is that instead of taking a single reduction discovered by one of passes, we'd better collect other
    successful discoveries from all passes and then merge them together - "fold". If a folded transformation passes
    the interestingness test, we make a much faster progress on reduction: we make a better use of parallelism (very
    often several workers discover multiple relatively small individual reductions) and we make all passes "collaborate"
    instead of "competing" with each other.

    Not always a fold passes the interestingness test; this class contains a workaround logic for such cases
    (heuristically "banning" transformations that might've lead to a failure).
    """

    # Controls how long should we keep scheduling regular/folding transform jobs before we "commit" to proceeding with
    # the best transformation found so far.
    #
    # This magic constant is chosen semi-arbitrarily. It shouldn't be too small to let us accumulate enough candidates
    # and attempt merging them. Neither should it be too large since the probability of a successful fold diminishes the
    # more candidates there are; also proceeding with a transformation often unblocks new reduction possibilities.
    JOB_COUNT_FACTOR = 10

    def __init__(self):
        self.folding_candidates: list[HintState] = []
        self.best_successful_fold: FoldingStateOut | None = None
        self.failed_folds: list[FoldingStateOut] = []
        self.attempted_folds: set[FoldingStateIn] = set()

    def on_transform_job_success(self, state: Any) -> None:
        if isinstance(state, HintState):
            # Add a new candidate for future folds. Note that only simple hint-based transformations are considered
            # eligible.
            self.folding_candidates.append(state)

    def on_transform_job_failure(self, state: Any) -> None:
        if isinstance(state, FoldingStateOut):
            # Remember the combination that didn't pass the interestingness test - we'll avoid it (in a fuzzy,
            # random-based sense) in future folds: see maybe_prepare_folding_job().
            self.failed_folds.append(state)

    def maybe_prepare_folding_job(self, job_order: int, best_success_state: Any) -> FoldingStateIn | None:
        if len(self.folding_candidates) < 2:
            # Nothing to fold.
            return None
        if len(self.attempted_folds) > job_order // 5:
            # Don't schedule folding jobs too frequently. TODO: replace the magic constant with a better formula.
            return None

        # We'll always take the hints from the best discovery so far. This gives us a good starting point - whatever we
        # add below should likely result in something that becomes the-new-best (if it passes the interestingness test).
        forcelist_states: set[HintState]
        match best_success_state:
            case HintState():
                forcelist_states = {best_success_state}
            case FoldingStateOut():
                forcelist_states = set(best_success_state.sub_states)
            case _:
                forcelist_states = set()

        # Heuristically avoid "bad" items (those that cause unsuccessful folds). For this, we look at previously failed
        # folds and "ban" randomly selected halves of them.
        banned_states: set[HintState] = set()
        for failed_fold in self.failed_folds:
            potential_ban = set(failed_fold.sub_states) - forcelist_states
            half = (len(potential_ban) + 1) // 2
            to_ban = random.sample(list(potential_ban), half)
            banned_states |= set(to_ban)

        to_fold = set(self.folding_candidates) - banned_states
        if len(to_fold) <= len(forcelist_states):
            # Couldn't compose a better combination than the previous best one.
            return None

        state = FoldingStateIn(sub_states=tuple(to_fold))
        if state in self.attempted_folds:
            # The same fold has already been attempted.
            return None
        self.attempted_folds.add(state)
        return state

    def continue_attempting_folds(self, job_order: int, parallel_tests: int, pass_count: int) -> bool:
        return job_order < self.JOB_COUNT_FACTOR * max(parallel_tests, pass_count)

    @staticmethod
    def transform(
        test_case: Path,
        state: FoldingStateIn,
        process_event_notifier,
        original_test_case: Path,
        written_paths: set[Path],
        *args,
        **kwargs,
    ) -> tuple[PassResult, FoldingStateOut | None]:
        report = HintBasedPass.load_and_apply_hints(original_test_case, test_case, state.sub_states)
        if report is None:
            return PassResult.INVALID, None
        written_paths.update(report.written_paths)
        return PassResult.OK, FoldingStateOut(
            sub_states=state.sub_states,
            size_delta_per_pass=report.stats_delta_per_pass,
            passes_ordered_by_delta=report.get_passes_ordered_by_delta(),
        )

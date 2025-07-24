"""Implements logic for folding (merging) multiple successful transformations."""

from copy import copy
from dataclasses import dataclass
from pathlib import Path
from typing import Any, List, Tuple, Union

from cvise.passes.abstract import PassResult
from cvise.passes.hint_based import HintBasedPass, HintState


@dataclass
class FoldingState:
    sub_states: List[HintState]


class FoldingManager:
    # Controls how long should we keep scheduling regular/folding transform jobs before we "commit" to proceeding with
    # the best transformation found so far.
    #
    # This magic constant is chosen semi-arbitrarily. It shouldn't be too small to let us accumulate enough candidates
    # and attempt merging them. Neither should it be too large since the probability of a successful fold diminishes the
    # more candidates there are; also proceeding with a transformation often unblocks new reduction possibilities.
    JOB_COUNT_FACTOR = 10

    def __init__(self):
        self.folding_candidates: List[HintState] = []
        self.folding_jobs = 0
        self.last_folding_job_size: Union[int, None] = None

    def on_transform_job_success(self, state: Any) -> None:
        if not isinstance(state, HintState):
            # We attempt folding only simple hint-based transformations.
            return
        self.folding_candidates.append(state)

    def maybe_prepare_folding_job(self, job_order: int) -> Union[FoldingState, None]:
        if len(self.folding_candidates) < 2:
            # Nothing to fold.
            return None
        if self.last_folding_job_size == len(self.folding_candidates):
            # The exact same fold was already attempted.
            return None
        if self.folding_jobs > job_order // 5:
            # Don't schedule folding jobs too frequently. TODO: replace the magic constant with a better formula.
            return None
        self.folding_jobs += 1
        self.last_folding_job_size = len(self.folding_candidates)
        return FoldingState(sub_states=copy(self.folding_candidates))

    def continue_attempting_folds(self, job_order: int, parallel_tests: int, pass_count: int) -> bool:
        return job_order < self.JOB_COUNT_FACTOR * max(parallel_tests, pass_count)

    @staticmethod
    def transform(test_case: Path, state: FoldingState, *args, **kwargs) -> Tuple[PassResult, List[HintState]]:
        HintBasedPass.load_and_apply_hints(test_case, state.sub_states)
        return PassResult.OK, state

import time
from typing import Optional

from cvise.passes.abstract import AbstractPass


class SinglePassStatistic:
    def __init__(self, pass_user_visible_name):
        self.pass_user_visible_name = pass_user_visible_name
        self.total_seconds: float = 0
        self.worked = 0
        self.failed = 0
        self.totally_executed = 0
        self.total_size_delta = 0


class PassStatistic:
    def __init__(self):
        self._stats: dict[str, SinglePassStatistic] = {}
        self._folding_stats = SinglePassStatistic('Folding')

    def add_initialized(self, pass_: AbstractPass, start_time: float) -> None:
        """Record a completion of a new() method for a pass."""
        stat = self._get_stats(pass_)
        stat.total_seconds += time.monotonic() - start_time

    def add_executed(self, pass_: Optional[AbstractPass], start_time: float, parallel_workers: int) -> None:
        """Record a completion of a transformation and checking task for a pass.

        If pass_ is None, it was a folding execution.
        """
        stat = self._get_stats(pass_)
        stat.totally_executed += 1
        # Account for parallelism when adding up durations.
        stat.total_seconds += (time.monotonic() - start_time) / parallel_workers

    def add_success(self, pass_: Optional[AbstractPass]):
        """Record that a transformation by the pass passes the interestingness test.

        If pass_ is None, it was a folding execution.
        """
        stat = self._get_stats(pass_)
        stat.worked += 1

    def add_failure(self, pass_: Optional[AbstractPass]):
        """Record that a transformation by the pass failed or didn't pass the interestingness test.

        If pass_ is None, it was a folding execution.
        """
        stat = self._get_stats(pass_)
        stat.failed += 1

    def add_committed_success(self, pass_name: Optional[str], size_delta: int):
        stat = self._stats[pass_name] if pass_name is not None else self._folding_stats
        stat.total_size_delta += size_delta

    @property
    def sorted_results(self):
        def sort_statistics(item: tuple[str, SinglePassStatistic]) -> tuple:
            pass_name, pass_data = item
            return (pass_data.total_size_delta, pass_data.total_seconds, pass_name)

        regular_results = sorted(self._stats.items(), key=sort_statistics)
        folding_results = []
        if self._folding_stats.worked > 0:
            folding_results.append(('Folding (merging transformations from other passes)', self._folding_stats))
        return regular_results + folding_results

    def _get_stats(self, pass_: Optional[AbstractPass]) -> SinglePassStatistic:
        if pass_ is None:
            return self._folding_stats
        name = pass_.user_visible_name()
        if name not in self._stats:
            self._stats[name] = SinglePassStatistic(name)
        return self._stats[name]

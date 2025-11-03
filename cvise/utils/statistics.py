from __future__ import annotations

import time

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
        self._start_time = time.monotonic()

    def add_initialized(self, pass_: AbstractPass, start_time: float, parallel_workers: int) -> None:
        """Record a completion of a new() method for a pass."""
        stat = self._get_stats(pass_)
        _add_duration(stat, start_time, parallel_workers)
        assert (
            sum(s.total_seconds for s in self._stats.values()) + self._folding_stats.total_seconds
            <= time.monotonic() - self._start_time
        )

    def add_executed(self, pass_: AbstractPass | None, start_time: float, parallel_workers: int) -> None:
        """Record a completion of a transformation and checking task for a pass.

        If pass_ is None, it was a folding execution.
        """
        stat = self._get_stats(pass_)
        stat.totally_executed += 1
        _add_duration(stat, start_time, parallel_workers)
        assert (
            sum(s.total_seconds for s in self._stats.values()) + self._folding_stats.total_seconds
            <= time.monotonic() - self._start_time
        )

    def add_aborted(
        self, pass_: AbstractPass | None, start_time: float, parallel_workers: int, is_transform: bool
    ) -> None:
        """Record an unfinished (canceled or timed out) job."""
        stat = self._get_stats(pass_)
        if is_transform:
            stat.totally_executed += 1
            stat.failed += 1
        _add_duration(stat, start_time, parallel_workers)
        assert (
            sum(s.total_seconds for s in self._stats.values()) + self._folding_stats.total_seconds
            <= time.monotonic() - self._start_time
        )

    def add_success(self, pass_: AbstractPass | None) -> None:
        """Record that a transformation by the pass passes the interestingness test.

        If pass_ is None, it was a folding execution.
        """
        stat = self._get_stats(pass_)
        assert stat.worked < stat.totally_executed
        stat.worked += 1

    def add_failure(self, pass_: AbstractPass | None) -> None:
        """Record that a transformation by the pass failed or didn't pass the interestingness test or returned STOP.

        If pass_ is None, it was a folding execution.
        """
        stat = self._get_stats(pass_)
        assert stat.failed < stat.totally_executed
        stat.failed += 1

    def add_committed_success(self, pass_name: str | None, size_delta: int) -> None:
        """Record that the transformation found by the pass was chosen by C-Vise to apply to the test case."""
        stat = self._stats[pass_name] if pass_name is not None else self._folding_stats
        stat.total_size_delta += size_delta

    @property
    def sorted_results(self) -> list[tuple[str, SinglePassStatistic]]:
        def sort_statistics(item: tuple[str, SinglePassStatistic]) -> tuple:
            pass_name, pass_data = item
            return (pass_data.total_size_delta, pass_data.total_seconds, pass_name)

        regular_results = sorted(self._stats.items(), key=sort_statistics)
        folding_results = []
        if self._folding_stats.worked > 0:
            folding_results.append(('Folding (merging transformations from other passes)', self._folding_stats))
        return regular_results + folding_results

    def _get_stats(self, pass_: AbstractPass | None) -> SinglePassStatistic:
        if pass_ is None:
            return self._folding_stats
        name = pass_.user_visible_name()
        if name not in self._stats:
            self._stats[name] = SinglePassStatistic(name)
        return self._stats[name]


def _add_duration(stat: SinglePassStatistic, start_time: float, parallel_workers: int) -> None:
    # Account for parallelism when adding up durations.
    stat.total_seconds += (time.monotonic() - start_time) / parallel_workers

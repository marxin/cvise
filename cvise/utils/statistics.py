import time

from cvise.passes.abstract import AbstractPass


class SinglePassStatistic:
    def __init__(self, pass_name):
        self.pass_name = pass_name
        self.total_seconds = 0
        self.worked = 0
        self.failed = 0
        self.totally_executed = 0


class PassStatistic:
    def __init__(self):
        self.stats = {}

    def add_initialized(self, pass_: AbstractPass, start_time: float) -> None:
        """Record a completion of a new() method for a pass."""
        pass_name = repr(pass_)
        if pass_name not in self.stats:
            self.stats[pass_name] = SinglePassStatistic(pass_name)
        self.stats[pass_name].total_seconds += time.monotonic() - start_time

    def add_executed(self, pass_: AbstractPass, start_time: float, parallel_workers: int) -> None:
        """Record a completion of a transformation and checking task for a pass."""
        pass_name = repr(pass_)
        stat = self.stats[pass_name]
        stat.totally_executed += 1
        # Account for parallelism when adding up durations.
        stat.total_seconds += (time.monotonic() - start_time) / parallel_workers

    def add_success(self, pass_):
        """Record that a transformation by the pass passes the interestingness test."""
        pass_name = repr(pass_)
        self.stats[pass_name].worked += 1

    def add_failure(self, pass_):
        """Record that a transformation by the pass failed or didn't pass the interestingness test."""
        pass_name = repr(pass_)
        self.stats[pass_name].failed += 1

    @property
    def sorted_results(self):
        def sort_statistics(item):
            pass_name, pass_data = item
            return (-pass_data.total_seconds, pass_name)

        return sorted(self.stats.items(), key=sort_statistics)

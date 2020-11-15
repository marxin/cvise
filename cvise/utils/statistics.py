import time


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
        self.last_pass_start = None
        self.last_pass_name = None

    def start(self, pass_):
        pass_name = repr(pass_)
        if pass_name not in self.stats:
            self.stats[pass_name] = SinglePassStatistic(pass_name)
        assert not self.last_pass_name
        self.last_pass_name = pass_name
        self.last_pass_start = time.monotonic()

    def stop(self, pass_):
        pass_name = repr(pass_)
        assert pass_name == self.last_pass_name
        self.stats[pass_name].total_seconds += time.monotonic() - self.last_pass_start
        self.last_pass_start = None
        self.last_pass_name = None

    def add_executed(self, pass_):
        pass_name = repr(pass_)
        self.stats[pass_name].totally_executed += 1

    def add_success(self, pass_):
        pass_name = repr(pass_)
        self.stats[pass_name].worked += 1

    def add_failure(self, pass_):
        pass_name = repr(pass_)
        self.stats[pass_name].failed += 1

    @property
    def sorted_results(self):
        def sort_statistics(item):
            pass_name, pass_data = item
            return (-pass_data.total_seconds, pass_name)

        return sorted(self.stats.items(), key=sort_statistics)

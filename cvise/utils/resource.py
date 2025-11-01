import time
from collections import deque


class TimeoutEstimator:
    """Estimates how long a job's timeout should be set, given the recent durations."""

    _HISTORY_LEN = 30
    _MEASUREMENT_LOWER_BOUND = 1  # seconds
    _MEASUREMENTS_MULTIPLIER = 10

    def __init__(self, initial_timeout: float):
        self._initial_timeout = initial_timeout
        self._recent_durations: deque[float] = deque(maxlen=self._HISTORY_LEN)

    def update(self, start_time: float) -> None:
        duration = time.monotonic() - start_time
        self._recent_durations.append(duration)

    def estimate(self) -> float:
        if not self._recent_durations:
            return self._initial_timeout  # not enough stats
        worst = max(self._recent_durations)
        estimation = self._MEASUREMENTS_MULTIPLIER * max(worst, self._MEASUREMENT_LOWER_BOUND)
        return min(estimation, self._initial_timeout)

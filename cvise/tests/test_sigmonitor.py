import contextlib
import gc
import multiprocessing
import multiprocessing.managers
import os
import queue
import signal
import threading
import time
import weakref
from collections.abc import Iterator

import pytest

from cvise.utils import sigmonitor

_SLEEP_INFINITY = 100


@pytest.fixture
def mpmanager() -> Iterator[multiprocessing.managers.SyncManager]:
    with multiprocessing.Manager() as manager:
        yield manager


@pytest.fixture
def process_ready_event(mpmanager: multiprocessing.managers.SyncManager) -> threading.Event:
    return mpmanager.Event()


@pytest.fixture
def process_result_queue(mpmanager: multiprocessing.managers.SyncManager) -> queue.Queue:
    return mpmanager.Queue()


@pytest.mark.parametrize(
    'signum,expected_exception', [(signal.SIGINT, KeyboardInterrupt), (signal.SIGTERM, SystemExit)]
)
def test_raise_exception_on_demand(
    process_ready_event: threading.Event,
    process_result_queue: queue.Queue,
    signum: int,
    expected_exception: BaseException,
):
    proc = multiprocessing.Process(
        target=_process_main_calling_retrigger,
        args=(process_ready_event, process_result_queue),
    )
    proc.start()
    process_ready_event.wait()

    assert proc.pid is not None
    os.kill(proc.pid, signum)

    with _assert_duration_less_than(_SLEEP_INFINITY / 2):
        proc.join()
    assert not process_result_queue.empty()
    assert process_result_queue.get() == expected_exception


@pytest.mark.parametrize(
    'signum,expected_exception', [(signal.SIGINT, KeyboardInterrupt), (signal.SIGTERM, SystemExit)]
)
def test_raise_exception_on_demand_signal_twice(
    process_ready_event: threading.Event,
    process_result_queue: queue.Queue,
    signum: int,
    expected_exception: BaseException,
):
    proc = multiprocessing.Process(
        target=_process_main_calling_retrigger,
        args=(process_ready_event, process_result_queue),
    )
    proc.start()
    process_ready_event.wait()

    assert proc.pid is not None
    for _ in range(2):
        os.kill(proc.pid, signum)

    with _assert_duration_less_than(_SLEEP_INFINITY / 2):
        proc.join()
    assert not process_result_queue.empty()
    assert process_result_queue.get() == expected_exception


def _process_main_calling_retrigger(process_ready_event: threading.Event, process_result_queue: queue.Queue):
    sigmonitor.init()
    assert not sigmonitor.get_future().done()
    process_ready_event.set()
    for _ in range(_SLEEP_INFINITY):
        time.sleep(1)
        try:
            sigmonitor.maybe_raise_exc()
        except BaseException as e:
            assert type(sigmonitor.get_future().exception(timeout=0)) is type(e)
            process_result_queue.put(type(e))
            return
    process_result_queue.put(None)


@contextlib.contextmanager
def _assert_duration_less_than(max_duration: float) -> Iterator[None]:
    start_time = time.monotonic()
    yield
    assert time.monotonic() - start_time < max_duration

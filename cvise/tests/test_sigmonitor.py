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
def test_raise_exception(
    process_ready_event: threading.Event,
    process_result_queue: queue.Queue,
    signum: int,
    expected_exception: BaseException,
):
    proc = multiprocessing.Process(
        target=_process_main_sleeping,
        args=(sigmonitor.Mode.RAISE_EXCEPTION, process_ready_event, process_result_queue),
    )
    proc.start()
    process_ready_event.wait()

    assert proc.pid is not None
    os.kill(proc.pid, signum)

    with _assert_duration_less_than(_SLEEP_INFINITY / 2):
        proc.join()
    assert not process_result_queue.empty()
    assert process_result_queue.get() == expected_exception


@pytest.mark.parametrize('signum', [signal.SIGINT, signal.SIGTERM])
def test_quick_exit(
    process_ready_event: threading.Event,
    process_result_queue: queue.Queue,
    signum: int,
):
    proc = multiprocessing.Process(
        target=_process_main_sleeping, args=(sigmonitor.Mode.QUICK_EXIT, process_ready_event, process_result_queue)
    )
    proc.start()
    process_ready_event.wait()

    assert proc.pid is not None
    os.kill(proc.pid, signum)

    with _assert_duration_less_than(_SLEEP_INFINITY / 2):
        proc.join()


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
        args=(sigmonitor.Mode.RAISE_EXCEPTION_ON_DEMAND, process_ready_event, process_result_queue),
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
        args=(sigmonitor.Mode.RAISE_EXCEPTION_ON_DEMAND, process_ready_event, process_result_queue),
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


@pytest.mark.parametrize(
    'signum,expected_exception', [(signal.SIGINT, KeyboardInterrupt), (signal.SIGTERM, SystemExit)]
)
def test_raise_exception_in_del(
    process_ready_event: threading.Event,
    process_result_queue: queue.Queue,
    signum: int,
    expected_exception: type[BaseException],
):
    proc = multiprocessing.Process(
        target=_process_main_sleeping_in_del,
        args=(sigmonitor.Mode.RAISE_EXCEPTION, process_ready_event, process_result_queue, expected_exception),
    )
    proc.start()
    process_ready_event.wait()

    assert proc.pid is not None
    os.kill(proc.pid, signum)

    with _assert_duration_less_than(_SLEEP_INFINITY / 2):
        proc.join()
    assert not process_result_queue.empty()
    assert process_result_queue.get() == ('del', None)
    assert not process_result_queue.empty()
    assert process_result_queue.get() == ('retrigger', expected_exception)


@pytest.mark.parametrize(
    'signum,expected_exception', [(signal.SIGINT, KeyboardInterrupt), (signal.SIGTERM, SystemExit)]
)
def test_raise_exception_in_finalize(
    process_ready_event: threading.Event,
    process_result_queue: queue.Queue,
    signum: int,
    expected_exception: BaseException,
):
    proc = multiprocessing.Process(
        target=_process_main_sleeping_in_finalize,
        args=(sigmonitor.Mode.RAISE_EXCEPTION, process_ready_event, process_result_queue, expected_exception),
    )
    proc.start()
    process_ready_event.wait()

    assert proc.pid is not None
    os.kill(proc.pid, signum)

    with _assert_duration_less_than(_SLEEP_INFINITY / 2):
        proc.join()
    assert not process_result_queue.empty()
    assert process_result_queue.get() == ('finalize', None)
    assert not process_result_queue.empty()
    assert process_result_queue.get() == ('retrigger', expected_exception)


def _process_main_sleeping(
    mode: sigmonitor.Mode, process_ready_event: threading.Event, process_result_queue: queue.Queue
):
    sigmonitor.init(mode)
    assert not sigmonitor.get_future().done()
    try:
        process_ready_event.set()
        time.sleep(_SLEEP_INFINITY)
    except BaseException as e:
        assert type(sigmonitor.get_future().exception(timeout=0)) is type(e)
        process_result_queue.put(type(e))
    else:
        process_result_queue.put(None)


def _process_main_calling_retrigger(
    mode: sigmonitor.Mode, process_ready_event: threading.Event, process_result_queue: queue.Queue
):
    sigmonitor.init(mode)
    assert not sigmonitor.get_future().done()
    process_ready_event.set()
    for _ in range(_SLEEP_INFINITY):
        time.sleep(1)
        try:
            sigmonitor.maybe_retrigger_action()
        except BaseException as e:
            assert type(sigmonitor.get_future().exception(timeout=0)) is type(e)
            process_result_queue.put(type(e))
            return
    process_result_queue.put(None)


def _process_main_sleeping_in_del(
    mode: sigmonitor.Mode,
    process_ready_event: threading.Event,
    process_result_queue: queue.Queue,
    expected_exception: type[BaseException],
):
    sigmonitor.init(mode)
    assert not sigmonitor.get_future().done()

    class A:
        def __del__(self):
            try:
                process_ready_event.set()
                for _ in range(_SLEEP_INFINITY):
                    time.sleep(1)
                    if sigmonitor.signal_observed_for_testing():
                        break
            except BaseException as e:
                process_result_queue.put(('del', type(e)))
            else:
                assert type(sigmonitor.get_future().exception(timeout=0)) is expected_exception
                process_result_queue.put(('del', None))

    A()
    gc.collect()  # ensure the A object is garbage-collected quickly
    try:
        sigmonitor.maybe_retrigger_action()
    except BaseException as e:
        process_result_queue.put(('retrigger', type(e)))
    else:
        process_result_queue.put(('retrigger', None))


def _process_main_sleeping_in_finalize(
    mode: sigmonitor.Mode,
    process_ready_event: threading.Event,
    process_result_queue: queue.Queue,
    expected_exception: type[BaseException],
):
    sigmonitor.init(mode)
    assert not sigmonitor.get_future().done()

    def finalizer():
        try:
            process_ready_event.set()
            for _ in range(_SLEEP_INFINITY):
                time.sleep(1)
                if sigmonitor.signal_observed_for_testing():
                    break
        except BaseException as e:
            process_result_queue.put(('finalize', type(e)))
        else:
            assert type(sigmonitor.get_future().exception(timeout=0)) is expected_exception
            process_result_queue.put(('finalize', None))

    class A:
        def __init__(self):
            self._finalizer = weakref.finalize(self, finalizer)

    A()
    gc.collect()  # ensure the A object is garbage-collected quickly
    try:
        sigmonitor.maybe_retrigger_action()
    except BaseException as e:
        process_result_queue.put(('retrigger', type(e)))
    else:
        process_result_queue.put(('retrigger', None))


@contextlib.contextmanager
def _assert_duration_less_than(max_duration: float) -> Iterator[None]:
    start_time = time.monotonic()
    yield
    assert time.monotonic() - start_time < max_duration

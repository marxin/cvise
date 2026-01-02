import multiprocessing
import os
import queue
import signal
import subprocess
import sys
import threading
import time
from collections.abc import Callable
from pathlib import Path

import pebble
import pytest

from cvise.utils.process import (
    MPContextHook,
    ProcessEvent,
    ProcessEventNotifier,
    ProcessEventType,
    ProcessKiller,
    ProcessMonitor,
)
from cvise.utils import sigmonitor


@pytest.fixture
def process_monitor():
    PARALLEL_TESTS = 10
    mpmanager = multiprocessing.Manager()
    with ProcessMonitor(mpmanager, parallel_tests=PARALLEL_TESTS) as process_monitor:
        yield process_monitor


@pytest.fixture(autouse=True)
def signal_monitor():
    sigmonitor.init()


@pytest.fixture
def process_killer():
    with ProcessKiller() as process_killer:
        yield process_killer


@pytest.fixture
def mp_context_hook(process_monitor: ProcessMonitor):
    return MPContextHook(process_monitor)


@pytest.fixture
def pid_queue() -> queue.Queue:
    return multiprocessing.Manager().Queue()


@pytest.fixture
def process_event_notifier(pid_queue: queue.Queue) -> ProcessEventNotifier:
    return ProcessEventNotifier(pid_queue)


def read_pid_queue(pid_queue: queue.Queue, expected_size: int) -> list[ProcessEvent]:
    result = []
    while len(result) < expected_size:
        result.append(pid_queue.get())
    with pytest.raises(queue.Empty):
        pid_queue.get(timeout=0.1)  # wait a little, to make the assertion a bit stronger (if there's an in-flight item)
    assert pid_queue.empty()
    return result


@pytest.mark.skipif(os.name != 'posix', reason='requires POSIX for command-line tools')
def test_run_process_success(process_event_notifier: ProcessEventNotifier, pid_queue: queue.Queue):
    stdout, stderr, returncode = process_event_notifier.run_process(['echo', 'foo'])

    assert stdout == b'foo\n'
    assert stderr == b''
    assert returncode == 0
    q = read_pid_queue(pid_queue, 2)
    assert q[0].type == ProcessEventType.STARTED
    assert q[0].child_pid == q[1].child_pid
    assert q[1].type == ProcessEventType.FINISHED


@pytest.mark.skipif(os.name != 'posix', reason='requires POSIX for command-line tools')
def test_run_process_slow(process_event_notifier: ProcessEventNotifier):
    stdout, stderr, returncode = process_event_notifier.run_process(
        'echo a && sleep 1 && echo b && sleep 1 && echo c', shell=True
    )

    assert stdout == b'a\nb\nc\n'
    assert stderr == b''
    assert returncode == 0


@pytest.mark.skipif(os.name != 'posix', reason='requires POSIX for command-line tools')
def test_run_process_nonzero_return_code(process_event_notifier: ProcessEventNotifier, pid_queue: queue.Queue):
    stdout, stderr, returncode = process_event_notifier.run_process(['false'])

    assert stdout == b''
    assert stderr == b''
    assert returncode == 1
    q = read_pid_queue(pid_queue, 2)
    assert q[0].type == ProcessEventType.STARTED
    assert q[0].child_pid == q[1].child_pid
    assert q[1].type == ProcessEventType.FINISHED


@pytest.mark.skipif(os.name != 'posix', reason='requires POSIX for command-line tools')
def test_run_process_stderr(process_event_notifier: ProcessEventNotifier):
    stdout, stderr, returncode = process_event_notifier.run_process(['cp'])

    assert stdout == b''
    assert stderr != b''
    assert returncode != 0


@pytest.mark.skipif(os.name != 'posix', reason='requires POSIX for command-line tools')
def test_run_process_pid(process_event_notifier: ProcessEventNotifier, pid_queue: queue.Queue):
    stdout, _stderr, returncode = process_event_notifier.run_process('echo $$', shell=True)

    assert returncode == 0
    q = read_pid_queue(pid_queue, 2)
    assert q[0].child_pid == q[1].child_pid == int(stdout.strip())


@pytest.mark.skipif(os.name != 'posix', reason='requires POSIX for command-line tools')
def test_run_process_finish_notification_after_exit(
    process_event_notifier: ProcessEventNotifier, pid_queue: queue.Queue
):
    INFINITY = 100
    SLEEP_DURATION = 1

    def thread_main():
        # Initially, just the start notification is seen.
        q1 = read_pid_queue(pid_queue, 1)
        assert q1[0].type == ProcessEventType.STARTED
        pid = q1[0].child_pid

        # Still so a bit later.
        time.sleep(SLEEP_DURATION)
        read_pid_queue(pid_queue, 0)

        # After killing the child, the finish notification is seen.
        os.kill(pid, signal.SIGTERM)
        q2 = read_pid_queue(pid_queue, 1)
        assert q2[0].type == ProcessEventType.FINISHED
        assert q2[0].child_pid == pid

    thread = threading.Thread(target=thread_main)
    thread.start()

    # This will finish once the background thread inspects the state and kills the child process.
    _stdout, _stderr, returncode = process_event_notifier.run_process(['sleep', str(INFINITY)])
    assert returncode != 0

    thread.join()


@pytest.mark.skipif(os.name != 'posix', reason='requires POSIX for command-line tools')
def test_run_process_stdin(process_event_notifier: ProcessEventNotifier):
    stdout, stderr, returncode = process_event_notifier.run_process(
        'cat', shell=True, stdin=subprocess.PIPE, input=b'foo'
    )

    assert stdout == b'foo'
    assert stderr == b''
    assert returncode == 0


@pytest.mark.skipif(os.name != 'posix', reason='requires POSIX for command-line tools')
def test_run_process_stdin_slow(process_event_notifier: ProcessEventNotifier):
    stdout, stderr, returncode = process_event_notifier.run_process(
        'sleep 3 && cat', shell=True, stdin=subprocess.PIPE, input=b'foo'
    )

    assert stdout == b'foo'
    assert stderr == b''
    assert returncode == 0


@pytest.mark.skipif(os.name != 'posix', reason='requires POSIX for command-line tools')
def test_run_process_timeout(process_event_notifier: ProcessEventNotifier, pid_queue: queue.Queue):
    TIMEOUT = 1
    CHILD_DURATION = 100

    start_time = time.monotonic()
    with pytest.raises(subprocess.TimeoutExpired):
        process_event_notifier.run_process(['sleep', str(CHILD_DURATION)], timeout=TIMEOUT)

    assert TIMEOUT <= time.monotonic() - start_time < CHILD_DURATION / 2
    q = read_pid_queue(pid_queue, 2)
    assert q[0].type == ProcessEventType.STARTED
    assert q[0].child_pid == q[1].child_pid
    assert q[1].type == ProcessEventType.FINISHED


@pytest.mark.skipif(os.name != 'posix', reason='requires POSIX for command-line tools')
def test_run_process_non_existing_command(process_event_notifier: ProcessEventNotifier, pid_queue: queue.Queue):
    with pytest.raises(FileNotFoundError):
        process_event_notifier.run_process(['nonexistingnonexisting'])

    read_pid_queue(pid_queue, 0)


@pytest.mark.skipif(os.name != 'posix', reason='requires POSIX for command-line tools')
def test_check_output_success(process_event_notifier: ProcessEventNotifier):
    stdout = process_event_notifier.check_output(['echo', 'foo'])
    assert stdout == b'foo\n'


@pytest.mark.skipif(os.name != 'posix', reason='requires POSIX for command-line tools')
def test_check_output_failure(process_event_notifier: ProcessEventNotifier):
    with pytest.raises(RuntimeError):
        process_event_notifier.check_output(['false'])


@pytest.mark.skipif(os.name != 'posix', reason='requires POSIX for command-line tools')
def test_process_ignoring_sigterm(process_event_notifier: ProcessEventNotifier):
    """Verify that we fall back to killing a process via SIGKILL if it ignores SIGTERM.

    The overall time to kill the child shouldn't exceed Pebble's term_timeout, so when we're working in a Pebble worker
    we have enough time to finish.
    """
    TIMEOUT = 1
    INFINITY = 100
    start_time = time.monotonic()
    with pytest.raises(subprocess.TimeoutExpired):
        process_event_notifier.run_process(f'trap "" TERM && sleep {INFINITY}', shell=True, timeout=TIMEOUT)
    assert time.monotonic() - start_time - TIMEOUT < pebble.CONSTS.term_timeout  # type: ignore


@pytest.mark.skipif(sys.platform not in ('darwin', 'linux'), reason='requires /dev/urandom')
def test_process_ignoring_sigterm_infinite_stdout(process_event_notifier: ProcessEventNotifier):
    """Verify that we fall back to killing a process via SIGKILL if it ignores SIGTERM.

    Unlike the test above, here the job also generates a lot of stdout - we want to verify that we don't deadlock due
    to the output exceeding the stdout's buffer.
    """
    TIMEOUT = 1
    start_time = time.monotonic()
    with pytest.raises(subprocess.TimeoutExpired):
        process_event_notifier.run_process('trap "" TERM && cat /dev/urandom', shell=True, timeout=TIMEOUT)
    assert time.monotonic() - start_time - TIMEOUT < pebble.CONSTS.term_timeout  # type: ignore


def test_process_monitor_worker_start_stop(process_monitor: ProcessMonitor, mp_context_hook: MPContextHook):
    """Verify that MPContextHook+ProcessMonitor track worker process creation and shutdown."""
    N = 10
    INFINITY = 100  # seconds
    with pebble.ProcessPool(max_workers=N, context=mp_context_hook) as pool:
        # Submit long-lasting jobs and verify workers are reported as active.
        for _ in range(N):
            pool.schedule(time.sleep, args=[INFINITY])
        _wait_until(lambda: len(process_monitor.get_worker_to_child_pids()) == N)
        pool.stop()
    # After workers termination, verify no active workers are reported.
    assert not process_monitor.get_worker_to_child_pids()


@pytest.mark.skipif(os.name != 'posix', reason='requires POSIX for command-line tools')
def test_process_monitor_child_pids(tmp_path: Path, process_monitor: ProcessMonitor, mp_context_hook: MPContextHook):
    """Verify that MPContextHook+ProcessMonitor track children spawned by worker processes."""
    N = 10

    flag_file = tmp_path / 'flag.txt'

    def all_children_reported():
        pids = process_monitor.get_worker_to_child_pids()
        return len(pids) == N and all(len(v) == 1 for v in pids.values())

    def all_children_empty():
        pids = process_monitor.get_worker_to_child_pids()
        return len(pids) == N and all(not v for v in pids.values())

    with pebble.ProcessPool(max_workers=N, context=mp_context_hook) as pool:
        # Submit long-lasting jobs and verify a child is reported for each worker.
        args = [
            process_monitor.pid_queue,
            f'until [ -e {flag_file} ]; do sleep 0.1; done',
            True,  # shell
        ]
        for _ in range(N):
            pool.schedule(_run_with_process_event_notifier, args=args)
        _wait_until(all_children_reported)

        # Let jobs complete and verify no children are reported.
        flag_file.touch()
        _wait_until(all_children_empty)


@pytest.mark.skipif(os.name != 'posix', reason='requires POSIX for command-line tools')
def test_process_monitor_stop_with_active_children(process_monitor: ProcessMonitor, mp_context_hook: MPContextHook):
    """Verify that MPContextHook+ProcessMonitor handles the termination of workers with active child processes."""
    N = 10
    INFINITY = 100  # seconds

    def all_children_reported():
        pids = process_monitor.get_worker_to_child_pids()
        return len(pids) == N and all(len(v) == 1 for v in pids.values())

    with pebble.ProcessPool(max_workers=N, context=mp_context_hook) as pool:
        # Submit long-lasting jobs and verify a child is reported for each worker.
        for _ in range(N):
            pool.schedule(_run_with_process_event_notifier, args=[process_monitor.pid_queue, ['sleep', str(INFINITY)]])
        _wait_until(all_children_reported)
        pool.stop()
    # After workers termination, verify no children are reported.
    assert not process_monitor.get_worker_to_child_pids()


@pytest.mark.skipif(os.name != 'posix', reason='requires POSIX for command-line tools')
def test_process_killer_simple(process_killer: ProcessKiller):
    INFINITY = 100  # seconds
    proc = subprocess.Popen(['sleep', str(INFINITY)])
    start_time = time.monotonic()
    process_killer.kill_process_tree(proc.pid)
    proc.wait()

    assert time.monotonic() - start_time < INFINITY / 2


@pytest.mark.skipif(os.name != 'posix', reason='requires POSIX for command-line tools')
def test_process_killer_many(process_killer: ProcessKiller):
    N = 10
    INFINITY = 100  # seconds
    procs = [subprocess.Popen(['sleep', str(INFINITY)]) for _ in range(N)]
    start_time = time.monotonic()
    for p in procs:
        process_killer.kill_process_tree(p.pid)
    for p in procs:
        p.wait()

    elapsed = time.monotonic() - start_time
    assert elapsed < INFINITY / 2
    # kills should be concurrent and not wait for each process the maximum time
    assert elapsed < ProcessKiller.TERM_TIMEOUT * N / 2


@pytest.mark.skipif(os.name != 'posix', reason='requires POSIX for command-line tools')
def test_process_killer_process_ignores_sigterm(process_killer: ProcessKiller):
    INFINITY = 100  # seconds
    proc = subprocess.Popen(f'trap "" TERM && sleep {INFINITY}', shell=True)
    start_time = time.monotonic()
    process_killer.kill_process_tree(proc.pid)
    proc.wait()

    assert time.monotonic() - start_time < INFINITY / 2


def _wait_until(predicate: Callable) -> None:
    while not predicate():
        time.sleep(0.1)


def _run_with_process_event_notifier(pid_queue: queue.Queue, *args):
    sigmonitor.init()
    ProcessEventNotifier(pid_queue).run_process(*args)

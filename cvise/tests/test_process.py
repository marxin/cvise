import multiprocessing
import os
import pebble
import pytest
import queue
import signal
import subprocess
import threading
import time
from typing import List

from cvise.utils.process import ProcessEvent, ProcessEventType, ProcessEventNotifier


@pytest.fixture
def pid_queue() -> multiprocessing.Queue:
    return multiprocessing.Queue()


@pytest.fixture
def process_event_notifier(pid_queue: multiprocessing.Queue) -> ProcessEventNotifier:
    return ProcessEventNotifier(pid_queue)


def read_pid_queue(pid_queue: multiprocessing.Queue, expected_size: int) -> List[ProcessEvent]:
    result = []
    while len(result) < expected_size:
        result.append(pid_queue.get())
    with pytest.raises(queue.Empty):
        pid_queue.get(timeout=0.1)  # wait a little, to make the assertion a bit stronger (if there's an in-flight item)
    assert pid_queue.empty()
    return result


@pytest.mark.skipif(os.name != 'posix', reason='requires POSIX for command-line tools')
def test_run_process_success(process_event_notifier: ProcessEventNotifier, pid_queue: multiprocessing.Queue):
    stdout, stderr, returncode = process_event_notifier.run_process(['echo', 'foo'])

    assert stdout == b'foo\n'
    assert stderr == b''
    assert returncode == 0
    q = read_pid_queue(pid_queue, 2)
    assert q[0].type == ProcessEventType.STARTED
    assert q[0].pid == q[1].pid
    assert q[1].type == ProcessEventType.FINISHED


@pytest.mark.skipif(os.name != 'posix', reason='requires POSIX for command-line tools')
def test_run_process_nonzero_return_code(
    process_event_notifier: ProcessEventNotifier, pid_queue: multiprocessing.Queue
):
    stdout, stderr, returncode = process_event_notifier.run_process(['false'])

    assert stdout == b''
    assert stderr == b''
    assert returncode == 1
    q = read_pid_queue(pid_queue, 2)
    assert q[0].type == ProcessEventType.STARTED
    assert q[0].pid == q[1].pid
    assert q[1].type == ProcessEventType.FINISHED


@pytest.mark.skipif(os.name != 'posix', reason='requires POSIX for command-line tools')
def test_run_process_stderr(process_event_notifier: ProcessEventNotifier):
    stdout, stderr, returncode = process_event_notifier.run_process(['cp'])

    assert stdout == b''
    assert stderr != b''
    assert returncode != 0


@pytest.mark.skipif(os.name != 'posix', reason='requires POSIX for command-line tools')
def test_run_process_pid(process_event_notifier: ProcessEventNotifier, pid_queue: multiprocessing.Queue):
    stdout, _stderr, returncode = process_event_notifier.run_process('echo $$', shell=True)

    assert returncode == 0
    q = read_pid_queue(pid_queue, 2)
    assert q[0].pid == q[1].pid == int(stdout.strip())


@pytest.mark.skipif(os.name != 'posix', reason='requires POSIX for command-line tools')
def test_run_process_finish_notification_after_exit(
    process_event_notifier: ProcessEventNotifier, pid_queue: multiprocessing.Queue
):
    INFINITY = 100
    SLEEP_DURATION = 1

    def thread_main():
        # Initially, just the start notification is seen.
        q1 = read_pid_queue(pid_queue, 1)
        assert q1[0].type == ProcessEventType.STARTED
        pid = q1[0].pid

        # Still so a bit later.
        time.sleep(SLEEP_DURATION)
        read_pid_queue(pid_queue, 0)

        # After killing the child, the finish notification is seen.
        os.kill(pid, signal.SIGTERM)
        q2 = read_pid_queue(pid_queue, 1)
        assert q2[0].type == ProcessEventType.FINISHED
        assert q2[0].pid == pid

    thread = threading.Thread(target=thread_main)
    thread.start()

    # This will finish once the background thread inspects the state and kills the child process.
    _stdout, _stderr, returncode = process_event_notifier.run_process(['sleep', str(INFINITY)])
    assert returncode != 0

    thread.join()


@pytest.mark.skipif(os.name != 'posix', reason='requires POSIX for command-line tools')
def test_run_process_timeout(process_event_notifier: ProcessEventNotifier, pid_queue: multiprocessing.Queue):
    TIMEOUT = 1
    CHILD_DURATION = 100

    start_time = time.monotonic()
    with pytest.raises(subprocess.TimeoutExpired):
        process_event_notifier.run_process(['sleep', str(CHILD_DURATION)], timeout=TIMEOUT)

    assert TIMEOUT <= time.monotonic() - start_time < CHILD_DURATION / 2
    q = read_pid_queue(pid_queue, 2)
    assert len(q) == 2
    assert q[0].type == ProcessEventType.STARTED
    assert q[0].pid == q[1].pid
    assert q[1].type == ProcessEventType.FINISHED


@pytest.mark.skipif(os.name != 'posix', reason='requires POSIX for command-line tools')
def test_run_process_non_existing_command(
    process_event_notifier: ProcessEventNotifier, pid_queue: multiprocessing.Queue
):
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
def test_process_ignoring_sigterm(process_event_notifier: ProcessEventNotifier, pid_queue: multiprocessing.Queue):
    """Verify that we fall back to killing a process via SIGKILL if it ignores SIGTERM.

    The overall time to kill the child shouldn't exceed Pebble's term_timeout, so when we're working in a Pebble worker
    we have enough time to finish.
    """
    TIMEOUT = 1
    INFINITY = 100
    start_time = time.monotonic()
    with pytest.raises(subprocess.TimeoutExpired):
        process_event_notifier.run_process(f'trap "" TERM && sleep {INFINITY}', shell=True, timeout=TIMEOUT)
    assert time.monotonic() - start_time - TIMEOUT < pebble.CONSTS.term_timeout

    q = read_pid_queue(pid_queue, 2)
    assert q[0].type == ProcessEventType.STARTED
    assert q[0].pid == q[1].pid
    assert q[1].type == ProcessEventType.FINISHED

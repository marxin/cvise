"""Helpers for interacting with child processes."""

import collections
import contextlib
from enum import auto, Enum, unique
import os
import multiprocessing
import pebble
import shlex
import subprocess
import threading
import time
from typing import Dict, Iterator, List, Mapping, Set, Tuple, Union

from cvise.utils import sigmonitor


@unique
class ProcessEventType(Enum):
    STARTED = auto()
    FINISHED = auto()


class ProcessEvent:
    def __init__(self, worker_pid, child_pid, event_type):
        self.worker_pid = worker_pid
        self.child_pid = child_pid
        self.type = event_type


class ProcessMonitor:
    """Keeps track of subprocesses spawned by Pebble workers."""

    def __init__(self, mpmanager: multiprocessing, parallel_tests: int):
        self.pid_queue = mpmanager.Queue()
        self._lock = threading.Lock()
        self._worker_to_child_pids: Dict[int, Set[int]] = {}
        # Remember dead worker PIDs, so that we can distinguish an early-reported child PID (arriving before
        # on_worker_started()) from a posthumously received child PID - the latter needs to be killed. The constant is
        # chosen to be big enough to make it practically unlikely to receive a new pid_queue event from a
        # forgotten-to-be-dead worker.
        self._recent_dead_workers: collections.deque[int] = collections.deque(maxlen=parallel_tests * 10)
        self._orphan_child_pids: Set[int] = set()
        self._thread = threading.Thread(target=self._thread_main)

    def __enter__(self):
        self._thread.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        # Notify the shutdown by putting a sentinel value to the queue, and wait until the background thread processes
        # all remaining items and quits.
        self.pid_queue.put(None)
        self._thread.join(timeout=60)  # semi-arbitrary timeout to prevent even theoretical possibility of deadlocks

    def on_worker_started(self, worker_pid: int) -> None:
        with self._lock:
            # Children might've been already added in _on_pid_queue_event() if the pid_queue event arrived early.
            self._worker_to_child_pids.setdefault(worker_pid, set())
            # It's rare but still possible that a new worker reuses the PID from a recently terminated one.
            with contextlib.suppress(ValueError):
                self._recent_dead_workers.remove(worker_pid)

    def on_worker_stopped(self, worker_pid: int) -> None:
        with self._lock:
            self._recent_dead_workers.append(worker_pid)
            self._orphan_child_pids |= self._worker_to_child_pids.pop(worker_pid)

    def get_orphan_child_pids(self) -> List[int]:
        with self._lock:
            return list(self._orphan_child_pids)

    def _thread_main(self) -> None:
        while True:
            item = self.pid_queue.get()
            if item is None:
                break
            self._on_pid_queue_event(item)

    def _on_pid_queue_event(self, event: ProcessEvent) -> None:
        with self._lock:
            posthumous = event.worker_pid in self._recent_dead_workers
            if not posthumous:
                # Update the worker's children PID set. The set might need to be created, since the pid_queue event
                # might've arrived before on_worker_started() gets called.
                children = self._worker_to_child_pids.setdefault(event.worker_pid, set())
                if event.type == ProcessEventType.STARTED:
                    children.add(event.child_pid)
                else:
                    children.discard(event.child_pid)


class MPContextHook:
    """Wrapper around multiprocessing.context, with hooks to track process lifetimes.

    Used in order to know Pebble worker PIDs and get notified about a worker's startup/finish.
    """

    def __init__(self, process_monitor: ProcessMonitor):
        self.__mp_context = multiprocessing.get_context()
        self.__process_monitor = process_monitor
        self.Process = lambda *args, **kwargs: MPProcessHook(self.__process_monitor, *args, **kwargs)

    def __getattr__(self, name):
        return getattr(self.__mp_context, name)


class MPProcessHook:
    """Wrapper around multiprocessing.Process, with hooks to track process lifetimes.

    Calls back into ProcessMonitor when the process is started or stopped.
    """

    def __init__(self, process_monitor: ProcessMonitor, *args, **kwargs):
        self.__process = multiprocessing.Process(*args, **kwargs)
        self.__process_monitor = process_monitor
        self.__stop_reported: bool = False

    def start(self):
        self.__process.start()
        self.__process_monitor.on_worker_started(self.pid)

    def join(self, *args):
        self.__process.join(*args)
        self.__maybe_report_stopped()

    def is_alive(self):
        alive = self.__process.is_alive()
        self.__maybe_report_stopped()
        return alive

    def __getattr__(self, name):
        return getattr(self.__process, name)

    def __maybe_report_stopped(self):
        if not self.__stop_reported and self.exitcode is not None:
            assert self.pid is not None
            self.__stop_reported = True
            self.__process_monitor.on_worker_stopped(self.pid)


class ProcessEventNotifier:
    """Runs a subprocess and reports its PID as start/finish events on the PID queue.

    Intended to be used in multiprocessing workers, to let the main process know the unfinished children subprocesses
    that should be killed.
    """

    def __init__(self, pid_queue):
        self._my_pid = os.getpid()
        self._pid_queue = pid_queue

    def run_process(
        self,
        cmd: Union[List[str], str],
        input: Union[bytes, None] = None,
        stdout: int = subprocess.PIPE,
        stderr: int = subprocess.PIPE,
        shell: bool = False,
        env: Union[Mapping[str, str], None] = None,
        timeout: Union[float, None] = None,
        **kwargs,
    ) -> Tuple[bytes, bytes, int]:
        if shell:
            assert isinstance(cmd, str)

        # Prevent signals from interrupting this "transaction": aborting it in the middle may result in spawning a
        # process without having its PID reported to the main C-Vise process, escaping resource controls.
        with sigmonitor.scoped_delay_signals():
            proc = subprocess.Popen(
                cmd,
                stdout=stdout,
                stderr=stderr,
                shell=shell,
                env=env,
                **kwargs,
            )
            self._notify_start(proc)

        # Try killing the process on exception (timeout/KeyboardInterrupt/SystemExit), and reporting the notify_finish
        # event too.
        with self._auto_notify_finish(proc):
            with _auto_kill(proc):
                stdout, stderr = proc.communicate(input=input, timeout=timeout)
                return stdout, stderr, proc.returncode

    def check_output(
        self,
        cmd: Union[List[str], str],
        input: Union[bytes, None] = None,
        stdout: int = subprocess.PIPE,
        stderr: int = subprocess.PIPE,
        shell: bool = False,
        env: Union[Mapping[str, str], None] = None,
        timeout: Union[float, None] = None,
        **kwargs,
    ) -> bytes:
        stdout, stderr, returncode = self.run_process(cmd, input, stdout, stderr, shell, env, timeout, **kwargs)
        if returncode != 0:
            stderr = stderr.decode('utf-8', 'ignore').strip()
            delim = ': ' if stderr else ''
            name = cmd[0] if isinstance(cmd, list) else shlex.split(cmd)[0]
            raise RuntimeError(f'{name} failed with exit code {returncode}{delim}{stderr}')
        return stdout

    def _notify_start(self, proc: subprocess.Popen) -> None:
        if not self._pid_queue:
            return
        self._pid_queue.put(
            ProcessEvent(worker_pid=self._my_pid, child_pid=proc.pid, event_type=ProcessEventType.STARTED)
        )

    @contextlib.contextmanager
    def _auto_notify_finish(self, proc: subprocess.Popen) -> Iterator[None]:
        try:
            yield
        finally:
            if self._pid_queue:
                self._pid_queue.put(
                    ProcessEvent(worker_pid=self._my_pid, child_pid=proc.pid, event_type=ProcessEventType.FINISHED)
                )


@contextlib.contextmanager
def _auto_kill(proc: subprocess.Popen) -> Iterator[None]:
    try:
        yield
    finally:
        if proc.returncode is None:
            _kill(proc)


def _kill(proc: subprocess.Popen) -> None:
    # First, close i/o streams opened for PIPE. This allows us to simply use wait() to wait for the process completion.
    # Additionally, it acts as another indication (SIGPIPE on *nix) for the process and its grandchildren to exit.
    if proc.stdin is not None:
        proc.stdin.close()
    if proc.stdout is not None:
        proc.stdout.close()
    if proc.stderr is not None:
        proc.stderr.close()

    # Second, attempt graceful termination (SIGTERM on *nix). We wait for some timeout that's less than Pebble's
    # term_timeout, so that we (hopefully) have time to try hard termination before C-Vise main process kills us.
    # Repeatedly request termination several times a second, because some programs "miss" incoming signals.
    TERMINATE_TIMEOUT = pebble.CONSTS.term_timeout / 2
    SLEEP_UNIT = 0.1  # semi-arbitrary
    stop_time = time.monotonic() + TERMINATE_TIMEOUT
    while True:
        proc.terminate()
        step_timeout = min(SLEEP_UNIT, stop_time - time.monotonic())
        if step_timeout <= 0:
            break
        try:
            proc.wait(timeout=step_timeout)
        except subprocess.TimeoutExpired:
            pass
        else:
            break
    if proc.returncode is not None:
        return

    # Third - if didn't exit on time - attempt a hard termination (SIGKILL on *nix).
    proc.kill()
    proc.wait()

"""Helpers for interacting with child processes."""

from __future__ import annotations
import collections
from concurrent.futures import ALL_COMPLETED, Future, wait
import contextlib
from dataclasses import dataclass, field
from enum import auto, Enum, unique
import heapq
import os
import multiprocessing
import multiprocessing.managers
import pebble
import psutil
import queue
import shlex
import subprocess
import threading
import time
from typing import Callable, Dict, Iterator, List, Mapping, Set, Tuple, Union

from cvise.utils import sigmonitor


_MPTaskLossWorkaroundObj: Union[MPTaskLossWorkaround, None] = None


@unique
class ProcessEventType(Enum):
    STARTED = auto()
    FINISHED = auto()
    ORPHANED = auto()  # reported instead of FINISHED when worker leaves the child process not terminated


class ProcessEvent:
    def __init__(self, worker_pid, child_pid, event_type):
        self.worker_pid = worker_pid
        self.child_pid = child_pid
        self.type = event_type


class ProcessMonitor:
    """Keeps track of subprocesses spawned by Pebble workers."""

    def __init__(self, mpmanager: multiprocessing.managers.SyncManager, parallel_tests: int):
        self.pid_queue: queue.Queue = mpmanager.Queue()
        self._lock = threading.Lock()
        self._worker_to_child_pids: Dict[int, Set[int]] = {}
        # Remember dead worker PIDs, so that we can distinguish an early-reported child PID (arriving before
        # on_worker_started()) from a posthumously received child PID - the latter needs to be killed. The constant is
        # chosen to be big enough to make it practically unlikely to receive a new pid_queue event from a
        # forgotten-to-be-dead worker.
        self._recent_dead_workers: collections.deque[int] = collections.deque(maxlen=parallel_tests * 10)
        self._thread = threading.Thread(target=self._thread_main)
        self._killer = ProcessKiller()

    def __enter__(self):
        self._killer.__enter__()
        self._thread.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        # Notify the shutdown by putting a sentinel value to the queue, and wait until the background thread processes
        # all remaining items and quits.
        self.pid_queue.put(None)
        self._thread.join(timeout=60)  # semi-arbitrary timeout to prevent even theoretical possibility of deadlocks
        self._killer.__exit__(exc_type, exc_val, exc_tb)

    def on_worker_started(self, worker_pid: int) -> None:
        with self._lock:
            # Children might've already been added in _on_pid_queue_event() if the pid_queue event arrived early.
            self._worker_to_child_pids.setdefault(worker_pid, set())
            # It's rare but still possible that a new worker reuses the PID from a recently terminated one.
            with contextlib.suppress(ValueError):
                self._recent_dead_workers.remove(worker_pid)

    def on_worker_stopped(self, worker_pid: int) -> None:
        with self._lock:
            self._recent_dead_workers.append(worker_pid)
            pids_to_kill = self._worker_to_child_pids.pop(worker_pid)

        for pid in pids_to_kill:
            self._killer.kill_process_tree(pid)

    def get_worker_to_child_pids(self) -> Dict[int, Set[int]]:
        with self._lock:
            return self._worker_to_child_pids.copy()

    def _thread_main(self) -> None:
        # Stop when receiving the sentinel (None).
        while item := self.pid_queue.get():
            self._on_pid_queue_event(item)

    def _on_pid_queue_event(self, event: ProcessEvent) -> None:
        with self._lock:
            posthumous = event.worker_pid in self._recent_dead_workers
            should_kill = posthumous or (event.type == ProcessEventType.ORPHANED)
            if not posthumous:
                # Update the worker's children PID set. The set might need to be created, since the pid_queue event
                # might've arrived before on_worker_started() gets called.
                children = self._worker_to_child_pids.setdefault(event.worker_pid, set())
                if event.type == ProcessEventType.STARTED:
                    children.add(event.child_pid)
                else:
                    children.discard(event.child_pid)

        if should_kill:
            self._killer.kill_process_tree(event.child_pid)


@dataclass(order=True, frozen=True)
class ProcessKillerTask:
    hard_kill: bool  # whether to kill() - as opposed to terminate()
    when: float  # seconds (in terms of the monotonic timer)
    proc: psutil.Process = field(compare=False)


class ProcessKiller:
    """Helper for terminating/killing process trees.

    For each process, we first try terminate() - SIGTERM on *nix - and if the process doesn't finish within TERM_TIMEOUT
    seconds we use kill() - SIGKILL on *nix. See also https://github.com/marxin/cvise/issues/145.
    """

    TERM_TIMEOUT = 3  # seconds
    EVENT_LOOP_STEP = 1  # seconds

    def __init__(self):
        # Essentially we implement a set of timers, one for each PID; since creating many threading.Timer would be too
        # costly, we use a single thread with an event queue instead.
        self._condition = threading.Condition()
        self._task_queue: List[ProcessKillerTask] = []
        self._shut_down: bool = False
        self._thread = threading.Thread(target=self._thread_main)

    def __enter__(self):
        self._thread.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        with self._condition:
            self._shut_down = True
            self._condition.notify()
        self._thread.join(timeout=60)  # semi-arbitrary timeout to prevent even theoretical possibility of deadlocks

    def kill_process_tree(self, pid: int) -> None:
        try:
            proc = psutil.Process(pid)
        except psutil.NoSuchProcess:
            return
        task = ProcessKillerTask(hard_kill=False, when=0, proc=proc)
        with self._condition:
            heapq.heappush(self._task_queue, task)
            self._condition.notify()

    def _thread_main(self) -> None:
        while True:
            with self._condition:
                if not self._task_queue and self._shut_down:
                    break
                if self._task_queue and not self._task_queue[0].proc.is_running():
                    # the process exited - nothing left for this task, and no need to wait if we're blocking shutdown
                    heapq.heappop(self._task_queue)
                    continue
                now = time.monotonic()
                timeout = min(self._task_queue[0].when - now, self.EVENT_LOOP_STEP) if self._task_queue else None
                if timeout is None or timeout > 0:
                    self._condition.wait(timeout)
                    continue
                task = heapq.heappop(self._task_queue)
            if task.hard_kill:
                self._do_hard_kill(task.proc)
            else:
                self._do_terminate(task.proc)

    def _do_terminate(self, proc: psutil.Process) -> None:
        try:
            children = proc.children(recursive=True) + [proc]
        except psutil.NoSuchProcess:
            return

        alive_children = []
        for child in children:
            try:
                child.terminate()
            except psutil.NoSuchProcess:
                pass
            else:
                alive_children.append(child)
        if not alive_children:
            return

        when = time.monotonic() + self.TERM_TIMEOUT
        with self._condition:
            for child in alive_children:
                task = ProcessKillerTask(hard_kill=True, when=when, proc=child)
                heapq.heappush(self._task_queue, task)
            self._condition.notify()

    def _do_hard_kill(self, proc: psutil.Process) -> None:
        try:
            children = proc.children(recursive=True) + [proc]
        except psutil.NoSuchProcess:
            return

        for child in children:
            with contextlib.suppress(psutil.NoSuchProcess):
                child.kill()


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

    def __init__(self, pid_queue: Union[queue.Queue, None]):
        self._my_pid = os.getpid()
        self._pid_queue = pid_queue

    def run_process(
        self,
        cmd: Union[List[str], str],
        shell: bool = False,
        input: Union[bytes, None] = None,
        stdout: int = subprocess.PIPE,
        stderr: int = subprocess.PIPE,
        env: Union[Mapping[str, str], None] = None,
        timeout: Union[float, None] = None,
        **kwargs,
    ) -> Tuple[bytes, bytes, int]:
        if shell:
            assert isinstance(cmd, str)

        # Prevent signals from interrupting in the middle of any operation besides proc.communicate() - abrupt exits
        # could result in spawning a child without having its PID reported or leaving the queue in inconsistent state.
        with sigmonitor.scoped_mode(sigmonitor.Mode.RAISE_EXCEPTION_ON_DEMAND):
            proc = subprocess.Popen(
                cmd,
                stdout=stdout,
                stderr=stderr,
                shell=shell,
                env=env,
                **kwargs,
            )
            self._notify_start(proc)

            with self._auto_notify_end(proc):
                # If a timeout was specified and the process exceeded it, we need to kill it - otherwise we'll leave a
                # zombie process on *nix. If it's KeyboardInterrupt/SystemExit, the worker will terminate soon, so we may
                # have not enough time to properly kill children, and zombies aren't a concern.
                with _auto_kill_on_timeout(proc):
                    with sigmonitor.scoped_mode(sigmonitor.Mode.RAISE_EXCEPTION):
                        stdout, stderr = proc.communicate(input=input, timeout=timeout)

        return stdout, stderr, proc.returncode

    def check_output(
        self,
        cmd: Union[List[str], str],
        shell: bool = False,
        input: Union[bytes, None] = None,
        stdout: int = subprocess.PIPE,
        stderr: int = subprocess.PIPE,
        env: Union[Mapping[str, str], None] = None,
        timeout: Union[float, None] = None,
        **kwargs,
    ) -> bytes:
        stdout, stderr, returncode = self.run_process(cmd, shell, input, stdout, stderr, env, timeout, **kwargs)
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
    def _auto_notify_end(self, proc: subprocess.Popen) -> Iterator[None]:
        try:
            yield
        finally:
            if self._pid_queue:
                event_type = ProcessEventType.ORPHANED if proc.returncode is None else ProcessEventType.FINISHED
                self._pid_queue.put(ProcessEvent(worker_pid=self._my_pid, child_pid=proc.pid, event_type=event_type))


class MPTaskLossWorkaround:
    """Workaround that attempts to prevent Pebble from losing scheduled tasks.

    The problematic scenario is when Pebble starts terminating a worker for a canceled taskA, but the worker manages to
    acknowledge the receipt of the next taskB shortly before dying - in that case taskB becomes associated with a
    non-existing worker and never finishes.

    Here we try to prevent this by scheduling "barrier" tasks, one for each worker, which report themselves as started
    and then sleep. If a task gets affected by the bug it won't report anything, which we detect via a hardcoded timeout
    and cancel all such "hung" tasks; at the end we notify all other tasks to complete. The expectation is that this
    procedure leaves the workers in a good state ready for regular C-Vise jobs.
    """

    _DEADLINE = 30  # seconds
    _POLL_LOOP_STEP = 0.1  # seconds

    def __init__(self, worker_count: int):
        self._worker_count = worker_count
        # Don't use Manager-based synchronization primitives, since they aren't exception-safe and hence won't work
        # properly when the worker receives a signal.
        self._task_status_queue = multiprocessing.SimpleQueue()
        self._task_exit_flag = multiprocessing.Event()

    def worker_process_initializer(self) -> Callable:
        """Returns a function to be called in a worker process in order to initialize global state needed later.

        Also is used to share non-managed multiprocessing synchronization primitives, which in the "forkserver" mode can
        only be done during process initialization.
        """
        return self._initialize_in_worker

    def execute(self, pool: pebble.ProcessPool) -> None:
        futures: List[Future] = [pool.schedule(self._job, args=[task_id]) for task_id in range(self._worker_count)]
        start_time = time.monotonic()
        task_procs: Dict[int, Union[psutil.Process, None]] = {}
        while len(task_procs) < self._worker_count:
            while not self._task_status_queue.empty():
                task_id, pid = self._task_status_queue.get()
                try:
                    task_procs[task_id] = psutil.Process(pid)
                except psutil.NoSuchProcess:
                    task_procs[task_id] = None
            timeout = min(self._POLL_LOOP_STEP, start_time + self._DEADLINE - time.monotonic())
            if timeout < 0:
                break
            time.sleep(timeout)
        self._task_exit_flag.set()
        start_time = time.monotonic()
        while time.monotonic() < start_time + self._DEADLINE:
            while not self._task_status_queue.empty():
                task_id, pid = self._task_status_queue.get()
                with contextlib.suppress(psutil.NoSuchProcess):
                    task_procs[task_id] = psutil.Process(pid)

            new_task_procs = {}
            for task_id, proc in task_procs.items():
                if proc and proc.is_running():
                    new_task_procs[task_id] = proc
                else:
                    futures[task_id].cancel()
            task_procs = new_task_procs

            _done, still_running = wait(futures, return_when=ALL_COMPLETED, timeout=self._POLL_LOOP_STEP)
            if not still_running:
                break
        for future in futures:  # is only necessary if the workaround didn't work out and we hit timeout
            future.cancel()
        self._task_exit_flag.clear()

    def _initialize_in_worker(self) -> None:
        global _MPTaskLossWorkaroundObj
        _MPTaskLossWorkaroundObj = self

    @staticmethod
    def _job(task_id: int) -> None:
        assert _MPTaskLossWorkaroundObj
        status_queue = _MPTaskLossWorkaroundObj._task_status_queue
        exit_flag = _MPTaskLossWorkaroundObj._task_exit_flag
        with sigmonitor.scoped_mode(sigmonitor.Mode.RAISE_EXCEPTION_ON_DEMAND):
            status_queue.put((task_id, os.getpid()))
            while not exit_flag.wait(timeout=MPTaskLossWorkaround._POLL_LOOP_STEP):
                sigmonitor.maybe_retrigger_action()


@contextlib.contextmanager
def _auto_kill_on_timeout(proc: subprocess.Popen) -> Iterator[None]:
    try:
        yield
    except subprocess.TimeoutExpired:
        _kill(proc)
        raise


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

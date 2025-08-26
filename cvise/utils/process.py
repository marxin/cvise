"""Helpers for interacting with child processes."""

import contextlib
from enum import auto, Enum, unique
import math
import pebble
import shlex
import subprocess
import time
from typing import Iterator, List, Mapping, Tuple, Union


@unique
class ProcessEventType(Enum):
    STARTED = auto()
    FINISHED = auto()


class ProcessEvent:
    def __init__(self, pid, event_type):
        self.pid = pid
        self.type = event_type


class ProcessEventNotifier:
    """Runs a subprocess and reports its PID as start/finish events on the PID queue.

    Intended to be used in multiprocessing workers, to let the main process know the unfinished children subprocesses
    that should be killed.
    """

    def __init__(self, pid_queue):
        self._pid_queue = pid_queue
        self._start_notified: bool = False

    def run_process(
        self,
        cmd: Union[List[str], str],
        stdout: int = subprocess.PIPE,
        stderr: int = subprocess.PIPE,
        shell: bool = False,
        env: Union[Mapping[str, str], None] = None,
        timeout: Union[int, None] = None,
        **kwargs,
    ) -> Tuple[bytes, bytes, int]:
        if shell:
            assert isinstance(cmd, str)
        proc = subprocess.Popen(
            cmd,
            stdout=stdout,
            stderr=stderr,
            shell=shell,
            env=env,
            **kwargs,
        )
        self._start_notified = False
        # Guarantee these postconditions regardless of exceptions occurring:
        # 1. The process is terminated.
        # 2. If notify_start was done, notify_finish was done too (after the process termination).
        with self._auto_notify_finish(proc):
            with _auto_kill(proc):
                self._notify_start(proc)
                stdout, stderr = proc.communicate(timeout=timeout)
                return stdout, stderr, proc.returncode

    def check_output(
        self,
        cmd: Union[List[str], str],
        stdout: int = subprocess.PIPE,
        stderr: int = subprocess.PIPE,
        shell: bool = False,
        env: Union[Mapping[str, str], None] = None,
        timeout: Union[int, None] = None,
        **kwargs,
    ) -> bytes:
        stdout, stderr, returncode = self.run_process(cmd, stdout, stderr, shell, env, timeout, **kwargs)
        if returncode != 0:
            stderr = stderr.decode('utf-8', 'ignore').strip()
            delim = ': ' if stderr else ''
            name = cmd[0] if isinstance(cmd, list) else shlex.split(cmd)[0]
            raise RuntimeError(f'{name} failed with exit code {returncode}{delim}{stderr}')
        return stdout

    def _notify_start(self, proc: subprocess.Popen) -> None:
        if not self._pid_queue:
            return
        self._pid_queue.put(ProcessEvent(proc.pid, ProcessEventType.STARTED))
        assert not self._start_notified
        self._start_notified = True

    @contextlib.contextmanager
    def _auto_notify_finish(self, proc: subprocess.Popen) -> Iterator[None]:
        try:
            yield
        finally:
            if self._start_notified and self._pid_queue:
                self._pid_queue.put(ProcessEvent(proc.pid, ProcessEventType.FINISHED))


@contextlib.contextmanager
def _auto_kill(proc: subprocess.Popen) -> Iterator[None]:
    try:
        yield
    finally:
        if proc.returncode is None:
            _kill(proc)


def _kill(proc: subprocess.Popen) -> None:
    # First, attempt graceful termination (SIGTERM on *nix). We wait for some timeout that's less than Pebble's
    # term_timeout, so that we have enough time to try other means before C-Vise main process kills us.
    proc.terminate()
    if _wait_till_exits(proc, pebble.CONSTS.term_timeout / 2):
        return
    # Second - if didn't exit on time - attempt a hard termination (SIGKILL on *nix).
    proc.kill()
    _wait_till_exits(proc)


def _wait_till_exits(proc: subprocess.Popen, timeout: Union[int, None]) -> bool:
    SLEEP_UNIT = 0.1  # semi-arbitrary
    stop_time = math.inf if timeout is None else time.monotonic() + timeout
    # Spin a loop with short communicate() calls. We don't use communicate(timeout) because this would block forever if
    # the stdout/stderr streams are kept open by grandchildren. We don't use wait() since it might deadlock if the child
    # overflows the stdout/stderr buffer by emitting lots of output.
    while proc.returncode is None and time.monotonic() <= stop_time:
        proc.terminate()
        with contextlib.suppress(subprocess.TimeoutExpired):
            proc.communicate(timeout=SLEEP_UNIT)
    return proc.returncode is not None

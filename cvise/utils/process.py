"""Helpers for interacting with child processes."""

import contextlib
from enum import auto, Enum, unique
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

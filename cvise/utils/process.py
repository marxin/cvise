"""Helpers for interacting with child processes."""

from contextlib import contextmanager
from enum import auto, Enum, unique
import shlex
import subprocess
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

    @contextmanager
    def _auto_notify_finish(self, proc: subprocess.Popen) -> Iterator[None]:
        try:
            yield
        finally:
            if self._start_notified and self._pid_queue:
                self._pid_queue.put(ProcessEvent(proc.pid, ProcessEventType.FINISHED))


@contextmanager
def _auto_kill(proc: subprocess.Popen) -> Iterator[None]:
    try:
        yield
    finally:
        if proc.returncode is None:
            _kill(proc)


def _kill(proc: subprocess.Popen) -> None:
    # First, attempt graceful termination (SIGTERM on *nix).
    try:
        proc.terminate()
        proc.communicate(timeout=5)  # semi-arbitrary timeout
    except subprocess.TimeoutExpired:
        # If didn't exit on time, attempt hard stop (SIGKILL on *nix).
        proc.kill()
        proc.communicate()

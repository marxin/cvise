"""Helper for setting up signal handlers and reliably propagating them.

There's no default SIGTERM handler, which doesn't allow doing proper cleanup on
shutdown. Additionally, while Python Standard Library already provides a default
handler for SIGINT that raises KeyboardInterrupt, in some cases it's not
propagated - e.g.:

> Due to the precarious circumstances under which __del__() methods are
> invoked, exceptions that occur during their execution are ignored, <...>

Such situations, while rare, would result in C-Vise not terminating on the
Ctrl-C keystroke. Additionally, many standard library functions don't perform
correct cleanup or even crash when an exception occurs in the middle of their
execution.

So instead of raising exceptions at arbitrary locations when a signal arrives,
we use deferred approach: the code should have "checkpoints" where it'd check if
a signal has arrived and raise an exception if so. We expose two interfaces (a
future-based and a file descriptor based) to allow code break from event loops.

Only when a termination signal arrives more than once (e.g., the user presses
Ctrl-C twice), we raise an exception synchronously.
"""

from __future__ import annotations

import atexit
import concurrent.futures
import contextlib
import os
import signal
import socket
from concurrent.futures import Future
from dataclasses import dataclass
from signal import SIGINT, SIGTERM


# Global singleton buffer used for reading wakeup sockets.
_SOCK_READ_BUF_SIZE = 1024


@dataclass(slots=True)
class _Context:
    """Holds the module singleton state after the init() is called."""

    future: Future
    read_buf: bytearray
    read_view: memoryview
    # File descriptors for triggering the "wakeup" whenever any signal arrives.
    wakeup_read_sock: socket.socket
    wakeup_write_sock: socket.socket
    # File descriptors for notifying SIGINT/SIGTERM specifically.
    sigintterm_read_sock: socket.socket
    sigintterm_write_sock: socket.socket
    # Whether a signal was observed that needs to be handled later.
    sigint_observed: bool = False
    sigterm_observed: bool = False


_context: _Context | None = None


def init(sigint: bool = True) -> None:
    global _context
    if _context is None:  # if called multiple times (typically in tests), only update flags
        wakeup_socks = socket.socketpair()
        sigintterm_socks = socket.socketpair()
        for socks in (wakeup_socks, sigintterm_socks):
            for sock in socks:
                sock.setblocking(False)

        read_buf = bytearray(_SOCK_READ_BUF_SIZE)
        _context = _Context(
            future=Future(),
            read_buf=read_buf,
            read_view=memoryview(read_buf),
            wakeup_read_sock=wakeup_socks[0],
            wakeup_write_sock=wakeup_socks[1],
            sigintterm_read_sock=sigintterm_socks[0],
            sigintterm_write_sock=sigintterm_socks[1],
        )

        signal.set_wakeup_fd(_context.wakeup_write_sock.fileno(), warn_on_full_buffer=False)
        atexit.register(_release_socks)

    assert _context is not None

    # Overwrite old signal handlers (in tests, the old handler could've been installed by ourselves as well; calling it
    # would result in an infinite recursion).
    signal.signal(SIGTERM, _on_signal)
    signal.signal(SIGINT, _on_signal if sigint else signal.SIG_IGN)


def maybe_raise_exc() -> None:
    """Raises an exception corresponding to a previously observed signal, if any."""
    assert _context
    # If multiple signals occurred, prefer SIGTERM.
    if _context.sigterm_observed:
        raise _create_exception(SIGTERM)
    elif _context.sigint_observed:
        raise _create_exception(SIGINT)


def get_future() -> Future:
    """Returns a future that's resolved with an exception when a SIGINT/SIGTERM signal arrives."""
    assert _context is not None
    return _context.future


def get_wakeup_sock() -> socket.socket:
    """Returns a socket that's populated with the numbers of arrived signals.

    Is intended to be used with select(); the handler should call handle_readable_wakeup_fd().
    """
    assert _context is not None
    return _context.wakeup_read_sock


def get_sigintterm_sock() -> socket.socket:
    """Returns a socket that's populated with opaque data when SIGINT/SIGTERM signals arrive.

    Is intended to be used with select() in conjunction with get_wakeup_sock(); the handler should call
    handle_readable_wakeup_fd() for both. This dedicated socket allows a program to have multiple select() loops as long
    as they don't consume the same dedicated pipe.
    """
    assert _context is not None
    return _context.sigintterm_read_sock


def handle_readable_wakeup_fd(sock: socket.socket) -> None:
    """To be called when the corresponding FD is readable."""
    # Drain the socket.
    assert _context is not None
    try:
        nbytes = os.readv(sock.fileno(), (_context.read_buf,))
    except OSError:
        return  # data was read by another thread or shutdown started

    # In case of the common wakeup FD, also set corresponding global flags and copy the notifications into the dedicated
    # sockets.
    if sock != _context.wakeup_read_sock:
        return
    contents = _context.read_view[:nbytes]
    if SIGINT in contents:
        _set_future_exception(_create_exception(SIGINT))
        _notify_sock(_context.sigintterm_write_sock)
    if SIGTERM in contents:
        _set_future_exception(_create_exception(SIGTERM))
        _notify_sock(_context.sigintterm_write_sock)


def signal_observed_for_testing() -> bool:
    assert _context is not None
    return _context.sigint_observed or _context.sigterm_observed


def _release_socks() -> None:
    if _context is None:
        return
    signal.set_wakeup_fd(-1)
    for sock in (
        _context.wakeup_read_sock,
        _context.wakeup_write_sock,
        _context.sigintterm_read_sock,
        _context.sigintterm_write_sock,
    ):
        sock.close()


def _notify_sock(sock: socket.socket) -> None:
    try:
        sock.send(b'\0')
    except BlockingIOError:
        pass  # discard the notification if the buffer is full - it's sufficient to have nonzero number of pending bytes


def _on_signal(signum: int, frame) -> None:
    assert _context
    repeated = _context.sigterm_observed or _context.sigint_observed
    if signum == SIGINT:
        _context.sigint_observed = True
    elif signum == SIGTERM:
        _context.sigterm_observed = True

    exc = _create_exception(signum)
    _set_future_exception(exc)
    if repeated:
        raise exc


def _create_exception(signum: int) -> BaseException:
    if signum == SIGINT:
        return KeyboardInterrupt()
    elif signum == SIGTERM:
        return SystemExit(1)
    else:
        raise ValueError(f'Unexpected signal {signum}')


def _set_future_exception(exc: BaseException) -> None:
    with contextlib.suppress(concurrent.futures.InvalidStateError):  # no done() to avoid races
        _context.future.set_exception(exc)

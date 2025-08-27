"""Helper for setting up signal handlers and reliably propagating them.

There's no default SIGTERM handler, which doesn't allow doing proper cleanup on
shutdown.

Meanwhile Python Standard Library already provides a default handler for SIGINT
that raises KeyboardInterrupt, in some cases it's not propagated - e.g.:

> Due to the precarious circumstances under which __del__() methods are
> invoked, exceptions that occur during their execution are ignored, <...>

Such situations, while rare, would result in C-Vise not terminating on the
Ctrl-C keystroke. This helper allows to prevent whether a signal was observer
and letting the code raise the exception to trigger the shutdown.
"""

from contextlib import contextmanager
import os
import signal
from typing import Callable, Dict, Iterator, Set


# Signals we monitor, in the preference order: SIGTERM is more "important".
_SIGNAL_TO_EXCEPTION = {
    signal.SIGTERM: lambda: SystemExit(1),
    signal.SIGINT: lambda: KeyboardInterrupt(),
}


_use_exceptions: bool = False
_original_signal_handlers: Dict[int, Callable] = {}
_observed_signals: Set[int] = set()


def init(use_exceptions: bool) -> None:
    global _use_exceptions
    _use_exceptions = use_exceptions
    # Install the new handler while remembering the previous/default one.
    for signum in _SIGNAL_TO_EXCEPTION.keys():
        handler = signal.signal(signum, _on_signal)
        if handler == signal.SIG_DFL and signum == signal.SIGINT:
            handler = signal.default_int_handler
        elif not callable(handler):
            continue
        _original_signal_handlers[signum] = handler


def maybe_retrigger_action() -> None:
    # If multiple signals occurred, prefer the one mentioned earlier (SIGTERM).
    for signum in _SIGNAL_TO_EXCEPTION.keys():
        if signum in _observed_signals:
            _trigger_signal_action(signum)
            return


@contextmanager
def scoped_use_exceptions() -> Iterator[None]:
    global _use_exceptions

    # It's unlikely to happen, but cheap to check: no need to enter the scope if we know we'll terminate afterwards.
    maybe_retrigger_action()

    assert not _use_exceptions
    try:
        _use_exceptions = True
        yield
    finally:
        _use_exceptions = False
        # If a signal occured within the scope, it's been propagated as an exception (letting the code in the scope do
        # resource cleanup) up to this level, but now that we're leaving the scope we should terminate the process
        # immediately instead.
        maybe_retrigger_action()


def _on_signal(signum: int, frame) -> None:
    # Prefer the original signal handler in case there's some nontrivial logic in it (e.g., not raising an exception
    # depending on stack frame contents).
    if _use_exceptions and signum in _original_signal_handlers:
        _original_signal_handlers[signum](signum, frame)
    else:
        _trigger_signal_action(signum)
    # no code after this point - the action above should've raised the exception or terminated the process


def _trigger_signal_action(signum: int) -> None:
    if _use_exceptions:
        raise _SIGNAL_TO_EXCEPTION[signum]()
    else:
        os._exit(1)
    # no code after this point - the action above should've raised the exception or terminated the process

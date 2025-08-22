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

import signal
from typing import Callable, Dict, Set


# Signals we monitor, in the preference order: SIGTERM is more "important".
_SIGNAL_TO_EXCEPTION = {
    signal.SIGTERM: lambda: SystemExit(1),
    signal.SIGINT: lambda: KeyboardInterrupt(),
}


_inited = False
_original_signal_handlers: Dict[int, Callable] = {}
_observed_signals: Set[int] = set()


def init():
    global _inited
    if _inited:
        return
    _inited = True
    # Install the new handler while remembering the previous one.
    for signum in _SIGNAL_TO_EXCEPTION.keys():
        handler = signal.signal(signum, _on_signal)
        if handler not in (signal.SIG_IGN, signal.SIG_DFL):
            assert callable(handler)
            _original_signal_handlers[signum] = handler


def maybe_reraise():
    assert _inited
    # If multiple signals occurred, prefer the one mentioned earlier (SIGTERM).
    for signum, exc_factory in _SIGNAL_TO_EXCEPTION.items():
        if signum in _observed_signals:
            raise exc_factory()


def _on_signal(signum, frame):
    _observed_signals.add(signum)
    # Prefer the original signal handler in case there's some nontrivial logic in it, but fall back to simply raising an
    # exception.
    if signum in _original_signal_handlers:
        _original_signal_handlers[signum](signum, frame)
    else:
        raise _SIGNAL_TO_EXCEPTION[signum]()
    # no code after this point - the signal handler above should've raised the exception

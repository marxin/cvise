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
import enum
import os
from pathlib import Path
import signal
from typing import Iterator
import weakref


@enum.unique
class Mode(enum.Enum):
    RAISE_EXCEPTION = enum.auto()
    QUICK_EXIT = enum.auto()
    RAISE_EXCEPTION_ON_DEMAND = enum.auto()


_mode: Mode = Mode.RAISE_EXCEPTION
_sigint_observed: bool = False
_sigterm_observed: bool = False


def init(mode: Mode) -> None:
    global _mode
    _mode = mode
    # Ignore old signal handlers (in tests, the old handler could've been installed by ourselves as well; calling it
    # would result in an infinite recursion).
    signal.signal(signal.SIGTERM, _on_signal)
    signal.signal(signal.SIGINT, _on_signal)


def maybe_retrigger_action() -> None:
    # If multiple signals occurred, prefer SIGTERM.
    if _sigterm_observed:
        _trigger_signal_action(signal.SIGTERM)
    elif _sigint_observed:
        _trigger_signal_action(signal.SIGINT)


@contextmanager
def scoped_mode(new_mode: Mode) -> Iterator[None]:
    global _mode

    # It's unlikely to happen, but cheap to check: no need to enter the scope if we know we'll terminate afterwards.
    _implicit_maybe_retrigger_action()

    previous_mode = _mode
    try:
        _mode = new_mode
        yield
    finally:
        _mode = previous_mode
        # Let the signals, if any, propagate according to the new mode.
        _implicit_maybe_retrigger_action()


def signal_observed_for_testing() -> bool:
    return _sigint_observed or _sigterm_observed


def _on_signal(signum: int, frame) -> None:
    global _sigint_observed
    global _sigterm_observed
    if signum == signal.SIGTERM:
        _sigterm_observed = True
    elif signum == signal.SIGINT:
        _sigint_observed = True

    if _is_on_demand_mode():
        return
    if _mode == Mode.RAISE_EXCEPTION and not _can_raise_in_frame(frame):
        # This is to avoid the "Exception ignored in" log spam.
        return
    # Prefer the standard signal handler in case there's some nontrivial logic in it (e.g., not raising an exception
    # depending on stack frame contents).
    if _mode == Mode.RAISE_EXCEPTION and signum == signal.SIGINT:
        signal.default_int_handler(signum, frame)
    else:
        _trigger_signal_action(signum)
    # no code after this point - the action above might've raised the exception or terminated the process


def _is_on_demand_mode() -> bool:
    return _mode == Mode.RAISE_EXCEPTION_ON_DEMAND


def _implicit_maybe_retrigger_action() -> None:
    if not _is_on_demand_mode():
        maybe_retrigger_action()


def _trigger_signal_action(signum: int) -> None:
    if _mode == Mode.QUICK_EXIT:
        os._exit(1)
    elif signum == signal.SIGTERM:
        raise SystemExit(1)
    elif signum == signal.SIGINT:
        raise KeyboardInterrupt()
    else:
        raise ValueError(f'Unexpected signal {signum}')
    # no code after this point - this is unreachable


def _can_raise_in_frame(frame) -> bool:
    while frame is not None:
        if frame.f_code:
            if frame.f_code.co_name == '__del__':
                return False
            if frame.f_code.co_filename and Path(frame.f_code.co_filename).stem == Path(weakref.__file__).stem:
                return False
        frame = frame.f_back
    return True

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

import concurrent.futures
import contextlib
import enum
import os
import signal
import weakref
from collections.abc import Iterator
from concurrent.futures import Future
from contextlib import contextmanager
from pathlib import Path
from typing import Optional


@enum.unique
class Mode(enum.Enum):
    RAISE_EXCEPTION = enum.auto()
    QUICK_EXIT = enum.auto()
    RAISE_EXCEPTION_ON_DEMAND = enum.auto()


_mode: Mode = Mode.RAISE_EXCEPTION
_sigint_observed: bool = False
_sigterm_observed: bool = False
_future: Optional[Future] = None


def init(mode: Mode) -> None:
    global _mode
    _mode = mode
    # Ignore old signal handlers (in tests, the old handler could've been installed by ourselves as well; calling it
    # would result in an infinite recursion).
    signal.signal(signal.SIGTERM, _on_signal)
    signal.signal(signal.SIGINT, _on_signal)

    global _future
    _future = Future()


def maybe_retrigger_action() -> None:
    # If multiple signals occurred, prefer SIGTERM.
    if _sigterm_observed:
        _trigger_signal_action(signal.SIGTERM, _create_exception(signal.SIGTERM))
    elif _sigint_observed:
        _trigger_signal_action(signal.SIGINT, _create_exception(signal.SIGINT))


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


def get_future() -> Future:
    assert _future is not None
    return _future


def signal_observed_for_testing() -> bool:
    return _sigint_observed or _sigterm_observed


def _on_signal(signum: int, frame) -> None:
    global _sigint_observed
    global _sigterm_observed
    match signum:
        case signal.SIGTERM:
            _sigterm_observed = True
        case signal.SIGINT:
            _sigint_observed = True

    exception = _create_exception(signum)
    # Set the exception on the future, unless it's already done. We don't use done() because it'd be potentially racy.
    with contextlib.suppress(concurrent.futures.InvalidStateError):
        _future.set_exception(exception)

    if _is_on_demand_mode():
        return
    match _mode:
        case Mode.RAISE_EXCEPTION if not _can_raise_in_frame(frame):
            # No immediate exception - to avoid the "Exception ignored in" log spam.
            return
        case Mode.RAISE_EXCEPTION if signum == signal.SIGINT:
            # Prefer the standard signal handler in case there's some nontrivial logic in it (e.g., not raising an
            # exception depending on stack frame contents).
            signal.default_int_handler(signum, frame)
        case _:
            _trigger_signal_action(signum, exception)
    # no code after this point - the action above might've raised the exception or terminated the process


def _is_on_demand_mode() -> bool:
    return _mode == Mode.RAISE_EXCEPTION_ON_DEMAND


def _implicit_maybe_retrigger_action() -> None:
    if not _is_on_demand_mode():
        maybe_retrigger_action()


def _trigger_signal_action(signum: int, exception: BaseException) -> None:
    if _mode == Mode.QUICK_EXIT:
        os._exit(1)
    else:
        raise exception
    # no code after this point - this is unreachable


def _create_exception(signum: int) -> BaseException:
    match signum:
        case signal.SIGINT:
            return KeyboardInterrupt()
        case signal.SIGTERM:
            return SystemExit(1)
        case _:
            raise ValueError('No signal')


def _can_raise_in_frame(frame) -> bool:
    while frame is not None:
        if frame.f_code:
            if frame.f_code.co_name == '__del__':
                return False
            if frame.f_code.co_filename and Path(frame.f_code.co_filename).stem == Path(weakref.__file__).stem:
                return False
        frame = frame.f_back
    return True

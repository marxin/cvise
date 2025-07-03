"""Helper for reraising KeyboardInterrupt on SIGINT when needed.

Meanwhile Python Standard Library already provides a default handler for SIGINT
that raises KeyboardInterrupt, in some cases it's not propagated - e.g.:

> Due to the precarious circumstances under which __del__() methods are
> invoked, exceptions that occur during their execution are ignored, <...>

Such situations, while rare, would result in C-Vise not terminating on the
Ctrl-C keystroke. This helper allows to prevent this by remembering whether
SIGINT was observed and letting the code raise the KeyboardInterrupt exception.
"""

import signal

inited = False
old_sigint_handler = None
sigint_observed = False


def init():
    global inited
    global old_sigint_handler
    if not inited:
        # Install the new handler while remembering the previous one.
        old_sigint_handler = signal.signal(signal.SIGINT, on_sigint)
        inited = True


def maybe_reraise():
    assert inited
    if sigint_observed:
        raise KeyboardInterrupt()


def on_sigint(signum, frame):
    global sigint_observed
    sigint_observed = True
    if old_sigint_handler:
        old_sigint_handler(signum, frame)
    else:
        signal.default_int_handler(signum, frame)
    # no code after this point - the signal handler above should've raised the exception

import sys

assert sys.platform != 'win32'

import termios  # noqa: E402
import select  # noqa: E402
from typing import List, Union  # noqa: E402


class KeyLogger:
    def __init__(self):
        self.fd = sys.stdin.fileno()
        self.old_term: Union[List, None] = None  # initialized in __enter__()

    def __enter__(self):
        try:
            new_term = termios.tcgetattr(self.fd)
            self.old_term = termios.tcgetattr(self.fd)

            # New terminal setting unbuffered
            new_term[3] = new_term[3] & ~termios.ICANON & ~termios.ECHO
            termios.tcsetattr(self.fd, termios.TCSAFLUSH, new_term)
        except termios.error:
            # this happens when run in pytest
            pass

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.old_term is not None:
            termios.tcsetattr(self.fd, termios.TCSAFLUSH, self.old_term)

    def _getch(self):
        return sys.stdin.read(1)

    def _kbhit(self):
        (dr, _dw, _de) = select.select([sys.stdin], [], [], 0)
        return dr != []

    def pressed_key(self) -> Union[str, None]:
        if self._kbhit():
            return self._getch()
        else:
            return None

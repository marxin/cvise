import sys

assert sys.platform == 'win32'

import msvcrt  # noqa: E402


class KeyLogger:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass

    def pressed_key(self) -> str | None:
        if msvcrt.kbhit():
            return msvcrt.getch().decode('utf-8')
        else:
            return None

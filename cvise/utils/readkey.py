import sys

if sys.platform == 'win32':
    from .readkey_windows import KeyLogger
else:
    from .readkey_posix import KeyLogger


__all__ = ['KeyLogger']

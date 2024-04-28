import os
import tempfile
from contextlib import contextmanager


def is_readable_file(filename):
    try:
        open(filename).read()
        return True
    except UnicodeDecodeError:
        return False


# TODO: use tempfile.NamedTemporaryFile(delete_on_close=False) since Python 3.12 is the oldest supported release
@contextmanager
def CloseableTemporaryFile(mode='w+b', dir=None):
    f = tempfile.NamedTemporaryFile(mode=mode, delete=False, dir=dir)
    try:
        yield f
    finally:
        os.remove(f.name)

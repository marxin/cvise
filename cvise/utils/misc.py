import os
import tempfile
from contextlib import contextmanager


def is_readable_file(filename):
    try:
        with open(filename) as f:
            f.read()
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
        # For Windows systems, be sure we always close the file before we remove it!
        if not f.closed:
            f.close()
        os.remove(f.name)

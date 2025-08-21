from contextlib import contextmanager
import os
from pathlib import Path
import tempfile
from typing import Iterator


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


# TODO: use contextlib.chdir once Python 3.11 is the oldest supported release
@contextmanager
def chdir(path: Path) -> Iterator[None]:
    original_workdir = os.getcwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(original_workdir)

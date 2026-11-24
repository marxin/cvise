"""Contains fixtures common across all Pytest tests, including the ones in subdirectories."""

import multiprocessing

import platform

import pytest


@pytest.fixture(scope='session', autouse=True)
def mp_start_method():
    """Configures the default multiprocessing method for all tests.

    The "forkserver" mode is the same as the one used by the C-Vise CLI.
    """
    # Enforce the method selection, in case the test framework previously set a different one.
    method = 'spawn' if platform.system() == 'Windows' else 'forkserver'
    multiprocessing.set_start_method(method, force=True)

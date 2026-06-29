import os
import time

import pytest

from cvise.utils import sigmonitor
from cvise.utils.process import ProcessEventNotifier


@pytest.mark.skipif(os.name != 'posix', reason='requires POSIX for command-line tools')
def test_run_process_orphaned_pipes_no_hang():
    """
    Regression test: Ensure that an orphaned background process keeping the stdout/stderr pipes open does not cause
    run_process to hang indefinitely when timeout=None.
    """
    sigmonitor.init()
    notifier = ProcessEventNotifier(pid_queue=None)

    # We use a subshell that launches a background sleep. The background process inherits the stdout/stderr pipes.
    # The main shell process will exit immediately, but without the fix, C-Vise would hang waiting for the pipes to
    # close.
    script = 'sleep 100 & exit 0'

    start_time = time.monotonic()

    stdout, stderr, returncode = notifier.run_process(['sh', '-c', script], timeout=None)

    elapsed = time.monotonic() - start_time

    # The process should exit almost immediately. If it hangs for 100 seconds, or times out via an external mechanism,
    # this will fail.
    assert elapsed < 10.0, f'run_process took {elapsed}s, likely hung on orphaned pipes!'
    assert returncode == 0

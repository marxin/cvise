"""Collects logs from multiprocessing workers and filters out canceled workers."""

from collections import deque
from contextlib import contextmanager
from dataclasses import dataclass
import logging
import logging.handlers
import multiprocessing
import threading
from typing import Callable, Iterator


class MPLogger:
    """Collects and processes logs from multiprocessing workers in the main process.

    Main features:
    * Discards logs from canceled jobs (to hide spurious errors from the user).
    * Supports logging to file (otherwise workers would try to write to the same file simultaneously).

    Each worker should use worker_process_initializer() and worker_process_job_wrapper().
    """

    def __init__(self, worker_count: int):
        self._lock = threading.Lock()
        # Use SimpleQueue and not Queue, because Pebble can terminate workers at an arbitrary time point, and Queue may
        # be corrupted if a process is killed while writing to it.
        self._queue = multiprocessing.SimpleQueue()
        self._thread = threading.Thread(target=self._main_process_thread_main, daemon=True)
        # Don't use indefinitely much memory to remember all canceled job orders throughout the whole C-Vise execution;
        # there's only worker_count workers at a time, but we store a few times more because logs are handled
        # asynchronously, after possibly new jobs have been started and canceled.
        self._job_orders_to_ignore = deque(maxlen=worker_count * 10)

    def __enter__(self):
        self._thread.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        # Notify the shutdown by putting a sentinel value to the queue, and wait until the background thread processes
        # all remaining items and quits.
        self._queue.put(None)
        self._thread.join(timeout=60)  # semi-arbitrary timeout to prevent even theoretical possibility of deadlocks

    def ignore_logs_from_job(self, job_order: int) -> None:
        """Remembers to ignore all logs coming from the specified job."""
        with self._lock:
            self._job_orders_to_ignore.append(job_order)

    def worker_process_initializer(self) -> Callable:
        """Returns a function to be called in a worker process in order to collect logs from it via IPC."""
        return _WorkerProcessInitializer(logging_level=logging.getLogger().getEffectiveLevel(), queue=self._queue)

    def _main_process_thread_main(self):
        """Receives logs from worker processes and either discards or processes them."""
        try:
            while True:
                record = self._queue.get()
                if record is None:
                    return
                if hasattr(record, 'job_order'):
                    with self._lock:
                        if record.job_order in self._job_orders_to_ignore:
                            continue
                logger = logging.getLogger(record.name)
                logger.handle(record)
        except:
            # On error, just drain the queue without any extra logic - an overflown queue would block a subprocess
            # that's trying to put items to it.
            while self._queue.get():
                pass
            raise


@contextmanager
def worker_process_job_wrapper(job_order: int) -> Iterator[None]:
    """Runs the given function with the logging configured to mark all logs with the job_order."""
    root = logging.getLogger()
    filter = _JobOrderAttachingFilter(job_order)
    root.addFilter(filter)
    try:
        yield
    finally:
        root.removeFilter(filter)


@dataclass
class _WorkerProcessInitializer:
    """The function-like object returned by worker_process_initializer()."""

    logging_level: int
    queue: multiprocessing.SimpleQueue

    def __call__(self):
        root = logging.getLogger()
        root.setLevel(self.logging_level)
        root.handlers.clear()
        root.addHandler(_QueueAppendingHandler(self.queue))


class _QueueAppendingHandler(logging.Handler):
    """Sends all logs into the IPC queue."""

    def __init__(self, queue: multiprocessing.SimpleQueue):
        super().__init__()
        self._queue = queue
        self._queue_handler = logging.handlers.QueueHandler(queue=None)

    def emit(self, record: logging.LogRecord):
        formatted_record = self._queue_handler.prepare(record)
        self._queue.put(formatted_record)


class _JobOrderAttachingFilter(logging.Filter):
    """Adds the job_order field to all log records.

    This is used in order to recognize and discard logs originating from already canceled jobs.
    """

    def __init__(self, job_order: int):
        super().__init__()
        self._job_order = job_order

    def filter(self, record: logging.LogRecord):
        record.job_order = self._job_order
        return True

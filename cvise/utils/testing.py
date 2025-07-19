from __future__ import annotations
from concurrent.futures import FIRST_COMPLETED, Future, wait
from dataclasses import dataclass
import difflib
from enum import auto, Enum, unique
import filecmp
import logging
import math
from multiprocessing import Manager
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import tempfile
import time
import traceback
from typing import Any, Callable, List, Union
import concurrent.futures

from cvise.cvise import CVise
from cvise.passes.abstract import AbstractPass, PassResult, ProcessEventNotifier, ProcessEventType
from cvise.utils import keyboard_interrupt_monitor
from cvise.utils.error import AbsolutePathTestCaseError
from cvise.utils.error import InsaneTestCaseError
from cvise.utils.error import InvalidInterestingnessTestError
from cvise.utils.error import InvalidTestCaseError
from cvise.utils.error import PassBugError
from cvise.utils.error import ZeroSizeError
from cvise.utils.misc import is_readable_file
from cvise.utils.readkey import KeyLogger
import pebble
import psutil

# change default Pebble sleep unit for faster response
pebble.common.SLEEP_UNIT = 0.01
MAX_PASS_INCREASEMENT_THRESHOLD = 3


@unique
class PassCheckingOutcome(Enum):
    """Outcome of checking the result of an invocation of a pass."""

    ACCEPT = auto()
    IGNORE = auto()
    STOP = auto()


def rmfolder(name):
    assert 'cvise' in str(name)
    try:
        shutil.rmtree(name)
    except OSError:
        pass


@dataclass
class InitEnvironment:
    pass_new: Callable
    test_case: str
    tmp_dir: Path
    job_timeout: int

    def run(self):
        return self.pass_new(self.test_case, tmp_dir=self.tmp_dir, job_timeout=self.job_timeout)


class TestEnvironment:
    def __init__(
        self,
        state,
        order,
        test_script,
        folder,
        test_case,
        all_test_cases,
        transform,
        pid_queue=None,
    ):
        self.state = state
        self.folder = folder
        self.base_size = None
        self.test_script = test_script
        self.exitcode = None
        self.result = None
        self.order = order
        self.transform = transform
        self.pid_queue = pid_queue
        self.pwd = os.getcwd()
        self.test_case = test_case
        self.base_size = test_case.stat().st_size
        self.all_test_cases = all_test_cases

        # Copy files to the created folder
        for test_case in all_test_cases:
            (self.folder / test_case.parent).mkdir(parents=True, exist_ok=True)
            shutil.copy2(test_case, self.folder / test_case.parent)

    @property
    def size_improvement(self):
        return self.base_size - self.test_case_path.stat().st_size

    @property
    def test_case_path(self):
        return self.folder / self.test_case

    @property
    def success(self):
        return self.result == PassResult.OK and self.exitcode == 0

    def dump(self, dst):
        for f in self.all_test_cases:
            shutil.copy(self.folder / f, dst)

        shutil.copy(self.test_script, dst)

    def run(self):
        try:
            # transform by state
            (result, self.state) = self.transform(
                str(self.test_case_path), self.state, ProcessEventNotifier(self.pid_queue)
            )
            self.result = result
            if self.result != PassResult.OK:
                return self

            # run test script
            self.exitcode = self.run_test(False)
            return self
        except OSError:
            # this can happen when we clean up temporary files for cancelled processes
            return self
        except Exception as e:
            print('Unexpected TestEnvironment::run failure: ' + str(e))
            traceback.print_exc()
            return self

    def run_test(self, verbose):
        try:
            os.chdir(self.folder)
            stdout, stderr, returncode = ProcessEventNotifier(self.pid_queue).run_process(
                str(self.test_script), shell=True
            )
            if verbose and returncode != 0:
                logging.debug('stdout:\n' + stdout)
                logging.debug('stderr:\n' + stderr)
        finally:
            os.chdir(self.pwd)
        return returncode


@unique
class PassStage(Enum):
    BEFORE_INIT = auto()
    IN_INIT = auto()
    ENUMERATING = auto()


@dataclass
class PassContext:
    """Stores runtime data for a currently active pass."""

    pass_: AbstractPass
    stage: PassStage
    # Stores pass-specific files to be used during transform jobs (e.g., hints generated during initialization), and
    # temporary folders for each transform job.
    temporary_root: Union[Path, None]
    # The pass state as returned by the pass new()/advance()/advance_on_success() methods.
    state: Any

    @staticmethod
    def create(pass_: AbstractPass) -> PassContext:
        pass_name = str(pass_).replace('::', '-')
        root = tempfile.mkdtemp(prefix=f'{TestManager.TEMP_PREFIX}{pass_name}-')
        logging.debug(f'Creating pass root folder: {root}')
        return PassContext(pass_=pass_, stage=PassStage.BEFORE_INIT, temporary_root=Path(root), state=None)

    def enumeration_finished(self) -> bool:
        return self.stage == PassStage.ENUMERATING and self.state is None


@unique
class JobType(Enum):
    INIT = auto()
    TRANSFORM = auto()


@dataclass
class Job:
    type: JobType
    future: Future
    pass_: AbstractPass
    pass_id: int
    start_time: float
    temporary_folder: Path


class TestManager:
    GIVEUP_CONSTANT = 50000
    MAX_TIMEOUTS = 20
    MAX_CRASH_DIRS = 10
    MAX_EXTRA_DIRS = 25000
    TEMP_PREFIX = 'cvise-'
    BUG_DIR_PREFIX = 'cvise_bug_'
    EVENT_LOOP_TIMEOUT = 1  # seconds

    def __init__(
        self,
        pass_statistic,
        test_script,
        timeout,
        save_temps,
        test_cases,
        parallel_tests,
        no_cache,
        skip_key_off,
        silent_pass_bug,
        die_on_pass_bug,
        print_diff,
        max_improvement,
        no_give_up,
        also_interesting,
        start_with_pass,
        skip_after_n_transforms,
        stopping_threshold,
    ):
        self.test_script = Path(test_script).absolute()
        self.timeout = timeout
        self.save_temps = save_temps
        self.pass_statistic = pass_statistic
        self.test_cases = set()
        self.test_cases_modes = {}
        self.parallel_tests = parallel_tests
        self.no_cache = no_cache
        self.skip_key_off = skip_key_off
        self.silent_pass_bug = silent_pass_bug
        self.die_on_pass_bug = die_on_pass_bug
        self.print_diff = print_diff
        self.max_improvement = max_improvement
        self.no_give_up = no_give_up
        self.also_interesting = also_interesting
        self.start_with_pass = start_with_pass
        self.skip_after_n_transforms = skip_after_n_transforms
        self.stopping_threshold = stopping_threshold

        for test_case in test_cases:
            test_case = Path(test_case)
            self.test_cases_modes[test_case] = test_case.stat().st_mode
            self.check_file_permissions(test_case, [os.F_OK, os.R_OK, os.W_OK], InvalidTestCaseError)
            if test_case.parent.is_absolute():
                raise AbsolutePathTestCaseError(test_case)
            self.test_cases.add(test_case)

        self.orig_total_file_size = self.total_file_size
        self.cache = {}
        self.pass_contexts: List[PassContext] = []
        if not self.is_valid_test(self.test_script):
            raise InvalidInterestingnessTestError(self.test_script)
        self.jobs: List[Job] = []
        self.order: int = 0

        self.use_colordiff = (
            sys.stdout.isatty()
            and subprocess.run(
                'colordiff --version',
                shell=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            ).returncode
            == 0
        )

    def remove_roots(self):
        if self.save_temps:
            return
        for ctx in self.pass_contexts:
            if not ctx.temporary_root:
                continue
            rmfolder(ctx.temporary_root)
            ctx.temporary_root = None

    def restore_mode(self):
        for test_case in self.test_cases:
            test_case.chmod(self.test_cases_modes[test_case])

    @classmethod
    def is_valid_test(cls, test_script):
        for mode in {os.F_OK, os.X_OK}:
            if not os.access(test_script, mode):
                return False
        return True

    @property
    def total_file_size(self):
        return self.get_file_size(self.test_cases)

    @property
    def sorted_test_cases(self):
        return sorted(self.test_cases, key=lambda x: x.stat().st_size, reverse=True)

    @staticmethod
    def get_file_size(files):
        return sum(f.stat().st_size for f in files)

    @property
    def total_line_count(self):
        return self.get_line_count(self.test_cases)

    @staticmethod
    def get_line_count(files):
        lines = 0
        for file in files:
            if is_readable_file(file):
                with open(file) as f:
                    lines += len([line for line in f.readlines() if line and not line.isspace()])
        return lines

    def backup_test_cases(self):
        for f in self.test_cases:
            orig_file = Path(f'{f}.orig')

            if not orig_file.exists():
                # Copy file and preserve attributes
                shutil.copy2(f, orig_file)

    @staticmethod
    def check_file_permissions(path, modes, error):
        for m in modes:
            if not os.access(path, m):
                if error is not None:
                    raise error(path, m)
                else:
                    return False

        return True

    @staticmethod
    def get_extra_dir(prefix, max_number):
        for i in range(0, max_number + 1):
            digits = int(round(math.log10(max_number), 0))
            extra_dir = Path(('{0}{1:0' + str(digits) + 'd}').format(prefix, i))

            if not extra_dir.exists():
                break

        # just bail if we've already created enough of these dirs, no need to
        # clutter things up even more...
        if extra_dir.exists():
            return None

        return extra_dir

    def report_pass_bug(self, job: Job, problem: str):
        """Create pass report bug and return True if the directory is created."""

        if not self.die_on_pass_bug:
            logging.warning(f'{job.pass_} has encountered a non fatal bug: {problem}')

        crash_dir = self.get_extra_dir(self.BUG_DIR_PREFIX, self.MAX_CRASH_DIRS)

        if crash_dir is None:
            return False

        crash_dir.mkdir()
        test_env: TestEnvironment = job.future.result()
        test_env.dump(crash_dir)

        if not self.die_on_pass_bug:
            logging.debug(
                f'Please consider tarring up {crash_dir} and creating an issue at https://github.com/marxin/cvise/issues and we will try to fix the bug.'
            )

        with (crash_dir / 'PASS_BUG_INFO.TXT').open(mode='w') as info_file:
            info_file.write(f'Package: {CVise.Info.PACKAGE_STRING}\n')
            info_file.write(f'Git version: {CVise.Info.GIT_VERSION}\n')
            info_file.write(f'LLVM version: {CVise.Info.LLVM_VERSION}\n')
            info_file.write(f'System: {str(platform.uname())}\n')
            info_file.write(PassBugError.MSG.format(job.pass_, problem, test_env.state, crash_dir))

        if self.die_on_pass_bug:
            raise PassBugError(job.pass_, problem, test_env.state, crash_dir)
        else:
            return True

    @staticmethod
    def diff_files(orig_file, changed_file):
        with open(orig_file) as f:
            orig_file_lines = f.readlines()

        with open(changed_file) as f:
            changed_file_lines = f.readlines()

        diffed_lines = difflib.unified_diff(orig_file_lines, changed_file_lines, str(orig_file), str(changed_file))

        return ''.join(diffed_lines)

    def check_sanity(self):
        logging.debug('perform sanity check... ')

        folder = Path(tempfile.mkdtemp(prefix=f'{self.TEMP_PREFIX}sanity-'))
        test_env = TestEnvironment(None, 0, self.test_script, folder, list(self.test_cases)[0], self.test_cases, None)
        logging.debug(f'sanity check tmpdir = {test_env.folder}')

        returncode = test_env.run_test(verbose=True)
        if returncode == 0:
            rmfolder(folder)
            logging.debug('sanity check successful')
        else:
            if not self.save_temps:
                rmfolder(folder)
            raise InsaneTestCaseError(self.test_cases, self.test_script)

    @classmethod
    def log_key_event(cls, event):
        logging.info(f'****** {event} ******')

    def kill_pid_queue(self):
        active_pids = set()
        while not self.pid_queue.empty():
            event = self.pid_queue.get()
            if event.type == ProcessEventType.FINISHED:
                active_pids.discard(event.pid)
            else:
                active_pids.add(event.pid)
        for pid in active_pids:
            try:
                process = psutil.Process(pid)
                children = process.children(recursive=True)
                children.append(process)
                for child in children:
                    try:
                        # Terminate the process more reliability: https://github.com/marxin/cvise/issues/145
                        child.kill()
                    except psutil.NoSuchProcess:
                        pass
            except psutil.NoSuchProcess:
                pass

    def release_job(self, job: Job) -> None:
        if not self.save_temps and job.temporary_folder is not None:
            rmfolder(job.temporary_folder)
        self.jobs.remove(job)

    def release_all_jobs(self) -> None:
        while self.jobs:
            self.release_job(self.jobs[0])

    def save_extra_dir(self, test_case_path):
        extra_dir = self.get_extra_dir('cvise_extra_', self.MAX_EXTRA_DIRS)
        if extra_dir is not None:
            os.mkdir(extra_dir)
            shutil.move(test_case_path, extra_dir)
            logging.info(f'Created extra directory {extra_dir} for you to look at later')

    def process_done_futures(self):
        quit_loop = False
        jobs_to_remove = []
        for job in self.jobs:
            # all items after first successfull (or a repeated error) should be cancelled
            if quit_loop:
                job.future.cancel()
                jobs_to_remove.append(job)
                continue

            if not job.future.done():
                continue

            if job.future.exception():
                # starting with Python 3.11: concurrent.futures.TimeoutError == TimeoutError
                if type(job.future.exception()) in (TimeoutError, concurrent.futures.TimeoutError):
                    self.timeout_count += 1
                    logging.warning('Test timed out.')
                    self.save_extra_dir(job.temporary_folder)
                    if self.timeout_count >= self.MAX_TIMEOUTS:
                        logging.warning('Maximum number of timeout were reached: %d' % self.MAX_TIMEOUTS)
                        quit_loop = True
                    jobs_to_remove.append(job)
                    continue
                else:
                    raise job.future.exception()

            if job.type == JobType.INIT:
                ctx = self.pass_contexts[job.pass_id]
                assert ctx.stage == PassStage.IN_INIT
                ctx.stage = PassStage.ENUMERATING
                ctx.state = job.future.result()
                self.pass_statistic.add_initialized(job.pass_, job.start_time)
                jobs_to_remove.append(job)
            elif job.type == JobType.TRANSFORM:
                outcome = self.check_pass_result(job)
                if outcome == PassCheckingOutcome.ACCEPT:
                    quit_loop = True
                else:
                    # account for statistics here as the entry is about to be deleted from self.jobs; for the ACCEPT
                    # case, this is done in wait_for_first_success().
                    self.pass_statistic.add_executed(job.pass_, job.start_time, self.parallel_tests)
                    if outcome == PassCheckingOutcome.STOP:
                        self.pass_contexts[job.pass_id].state = None
                    jobs_to_remove.append(job)
            else:
                raise ValueError(f'Unexpected job type {job.type}')

        for job in jobs_to_remove:
            self.release_job(job)

        return quit_loop

    def wait_for_first_success(self) -> Union[Job, None]:
        for job in self.jobs:
            if job.type != JobType.TRANSFORM:
                continue
            try:
                while not job.future.done():
                    # wait with a timeout, so that keyboard events can be handled reasonably quickly.
                    wait([job.future], timeout=self.EVENT_LOOP_TIMEOUT)
                    keyboard_interrupt_monitor.maybe_reraise()
                outcome = self.check_pass_result(job)
                if outcome == PassCheckingOutcome.ACCEPT:
                    self.pass_statistic.add_executed(job.pass_, job.start_time, self.parallel_tests)
                    return job
            # starting with Python 3.11: concurrent.futures.TimeoutError == TimeoutError
            except (TimeoutError, concurrent.futures.TimeoutError):
                pass
        return None

    def check_pass_result(self, job: Job):
        test_env: TestEnvironment = job.future.result()
        if test_env.success:
            if self.max_improvement is not None and test_env.size_improvement > self.max_improvement:
                logging.debug(f'Too large improvement: {test_env.size_improvement} B')
                return PassCheckingOutcome.IGNORE
            # Report bug if transform did not change the file
            if filecmp.cmp(self.current_test_case, test_env.test_case_path):
                if not self.silent_pass_bug:
                    if not self.report_pass_bug(job, 'pass failed to modify the variant'):
                        return PassCheckingOutcome.STOP
                return PassCheckingOutcome.IGNORE
            return PassCheckingOutcome.ACCEPT

        self.pass_statistic.add_failure(job.pass_)
        if test_env.result == PassResult.OK:
            assert test_env.exitcode
            if self.also_interesting is not None and test_env.exitcode == self.also_interesting:
                self.save_extra_dir(test_env.test_case_path)
        elif test_env.result == PassResult.STOP:
            return PassCheckingOutcome.STOP
        elif test_env.result == PassResult.ERROR:
            if not self.silent_pass_bug:
                self.report_pass_bug(job, 'pass error')
                return PassCheckingOutcome.STOP

        if not self.no_give_up and test_env.order > self.GIVEUP_CONSTANT:
            if not self.giveup_reported:
                self.report_pass_bug(job, 'pass got stuck')
                self.giveup_reported = True
            return PassCheckingOutcome.STOP
        return PassCheckingOutcome.IGNORE

    @classmethod
    def terminate_all(cls, pool):
        pool.stop()
        pool.join()

    def run_parallel_tests(self) -> Union[Job, None]:
        assert not self.jobs
        with pebble.ProcessPool(max_workers=self.parallel_tests) as pool:
            try:
                self.order = 1
                next_pass_id = 0
                self.timeout_count_per_pass = {}
                self.giveup_reported = False
                while self.jobs or any(not c.enumeration_finished() for c in self.pass_contexts):
                    keyboard_interrupt_monitor.maybe_reraise()

                    # schedule new jobs in the round-robin fashion, as long as there are free workers
                    while len(self.jobs) < self.parallel_tests and any(
                        self.can_schedule_for_pass(c) for c in self.pass_contexts
                    ):
                        self.maybe_schedule_init(pool, next_pass_id)
                        self.maybe_schedule_transform(pool, next_pass_id)
                        next_pass_id = (next_pass_id + 1) % len(self.pass_contexts)

                    # no more jobs could be scheduled at the moment - wait for some results
                    wait([j.future for j in self.jobs], return_when=FIRST_COMPLETED, timeout=self.EVENT_LOOP_TIMEOUT)
                    if self.process_done_futures():
                        break

                success = self.wait_for_first_success()
                self.terminate_all(pool)
                # Unfinished initializations will need to be restarted in the next round.
                for ctx in self.pass_contexts:
                    if ctx.stage == PassStage.IN_INIT:
                        ctx.stage = PassStage.BEFORE_INIT

                return success
            except:
                # Abort running jobs - by default the process pool waits for the ongoing jobs' completion.
                self.terminate_all(pool)
                raise

    def run_passes(self, passes):
        if self.start_with_pass:
            current_pass_names = [str(c.pass_) for c in self.pass_contexts]
            if self.start_with_pass in current_pass_names:
                self.start_with_pass = None
            else:
                return

        self.pass_contexts = []
        for pass_ in passes:
            self.pass_contexts.append(PassContext.create(pass_))
        self.jobs = []
        m = Manager()
        self.pid_queue = m.Queue()
        cache_key = repr([c.pass_ for c in self.pass_contexts])

        pass_titles = ', '.join(repr(c.pass_) for c in self.pass_contexts)
        logging.info(f'===< {pass_titles} >===')

        if self.total_file_size == 0:
            raise ZeroSizeError(self.test_cases)

        if not self.skip_key_off:
            logger = KeyLogger()

        try:
            for test_case in self.sorted_test_cases:
                self.current_test_case = test_case
                starting_test_case_size = test_case.stat().st_size
                success_count = 0

                if self.get_file_size([test_case]) == 0:
                    continue

                if not self.no_cache:
                    with open(test_case, mode='rb+') as tmp_file:
                        test_case_before_pass = tmp_file.read()

                        if cache_key in self.cache and test_case_before_pass in self.cache[cache_key]:
                            tmp_file.seek(0)
                            tmp_file.truncate(0)
                            tmp_file.write(self.cache[cache_key][test_case_before_pass])
                            logging.info(f'cache hit for {test_case}')
                            continue

                self.skip = False
                while any(not c.enumeration_finished() for c in self.pass_contexts) and not self.skip:
                    # Ignore more key presses after skip has been detected
                    if not self.skip_key_off and not self.skip:
                        key = logger.pressed_key()
                        if key == 's':
                            self.skip = True
                            self.log_key_event('skipping the rest of this pass')
                        elif key == 'd':
                            self.log_key_event('toggle print diff')
                            self.print_diff = not self.print_diff

                    success_job = self.run_parallel_tests()
                    self.kill_pid_queue()

                    if success_job:
                        self.process_result(success_job)
                        success_count += 1

                    # if the file increases significantly, bail out the current pass
                    test_case_size = self.current_test_case.stat().st_size
                    if test_case_size >= MAX_PASS_INCREASEMENT_THRESHOLD * starting_test_case_size:
                        logging.info(
                            f'skipping the rest of the pass (huge file increasement '
                            f'{MAX_PASS_INCREASEMENT_THRESHOLD * 100}%)'
                        )
                        break

                    self.release_all_jobs()
                    if not success_job:
                        break

                    # skip after N transformations if requested
                    skip_rest = self.skip_after_n_transforms and success_count >= self.skip_after_n_transforms
                    if len(self.pass_contexts) == 1:  # max-transforms is only supported for non-interleaving passes
                        if (
                            self.pass_contexts[0].pass_.max_transforms
                            and success_count >= self.pass_contexts[0].pass_.max_transforms
                        ):
                            skip_rest = True
                    if skip_rest:
                        logging.info(f'skipping after {success_count} successful transformations')
                        break

                # Cache result of this pass
                if not self.no_cache:
                    with open(test_case, mode='rb') as tmp_file:
                        if cache_key not in self.cache:
                            self.cache[cache_key] = {}

                        self.cache[cache_key][test_case_before_pass] = tmp_file.read()

            self.restore_mode()
            self.remove_roots()
        except KeyboardInterrupt:
            logging.info('Exiting now ...')
            self.remove_roots()
            sys.exit(1)

    def process_result(self, job: Job) -> None:
        test_env: TestEnvironment = job.future.result()
        if self.print_diff:
            diff_str = self.diff_files(self.current_test_case, test_env.test_case_path)
            if self.use_colordiff:
                diff_str = subprocess.check_output('colordiff', shell=True, encoding='utf8', input=diff_str)
            logging.info(diff_str)

        try:
            shutil.copy(test_env.test_case_path, self.current_test_case)
        except FileNotFoundError:
            raise RuntimeError(
                f"Can't find {self.current_test_case} -- did your interestingness test move it?"
            ) from None

        for pass_id, context in enumerate(self.pass_contexts):
            # For the pass that succeeded, continue from the state returned by its transform() that led to the success;
            # for other passes, continue the iteration from where the last advance() stopped.

            old_state = test_env.state if pass_id == job.pass_id else context.state
            context.state = (
                None
                if old_state is None
                else context.pass_.advance_on_success(test_env.test_case_path, old_state, job_timeout=self.timeout)
            )
        self.pass_statistic.add_success(job.pass_)

        pct = 100 - (self.total_file_size * 100.0 / self.orig_total_file_size)
        notes = []
        notes.append(f'{round(pct, 1)}%')
        notes.append(f'{self.total_file_size} bytes')
        if self.total_line_count:
            notes.append(f'{self.total_line_count} lines')
        if len(self.test_cases) > 1:
            notes.append(str(test_env.test_case))

        logging.info('(' + ', '.join(notes) + ')')

    def can_schedule_for_pass(self, ctx: PassContext) -> bool:
        return ctx.stage == PassStage.BEFORE_INIT or ctx.state is not None

    def maybe_schedule_init(self, pool: pebble.ProcessPool, pass_id: int) -> None:
        ctx = self.pass_contexts[pass_id]
        if ctx.stage != PassStage.BEFORE_INIT:
            return

        env = InitEnvironment(
            pass_new=ctx.pass_.new,
            test_case=self.current_test_case,
            tmp_dir=ctx.temporary_root,
            job_timeout=self.timeout,
        )
        future = pool.schedule(env.run)
        self.jobs.append(
            Job(
                type=JobType.INIT,
                future=future,
                pass_=ctx.pass_,
                pass_id=pass_id,
                start_time=time.monotonic(),
                temporary_folder=None,
            )
        )
        ctx.stage = PassStage.IN_INIT

    def maybe_schedule_transform(self, pool: pebble.ProcessPool, pass_id: int) -> None:
        ctx = self.pass_contexts[pass_id]
        if ctx.state is None:
            # Not initialized yet or already advanced through all states.
            return

        folder = Path(tempfile.mkdtemp(prefix=self.TEMP_PREFIX, dir=ctx.temporary_root))
        env = TestEnvironment(
            ctx.state,
            self.order,
            self.test_script,
            folder,
            self.current_test_case,
            self.test_cases,
            ctx.pass_.transform,
            self.pid_queue,
        )
        future = pool.schedule(env.run, timeout=self.timeout)
        self.jobs.append(
            Job(
                type=JobType.TRANSFORM,
                future=future,
                pass_=ctx.pass_,
                pass_id=pass_id,
                start_time=time.monotonic(),
                temporary_folder=folder,
            )
        )

        self.order += 1
        ctx.state = ctx.pass_.advance(self.current_test_case, ctx.state)

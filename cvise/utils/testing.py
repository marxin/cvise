from concurrent.futures import FIRST_COMPLETED, TimeoutError, wait
import difflib
import filecmp
import logging
import math
from multiprocessing import Manager
import os
import os.path
import platform
import shutil
import subprocess
import sys
import tempfile
import traceback

from cvise.cvise import CVise
from cvise.passes.abstract import PassResult, ProcessEventNotifier, ProcessEventType
from cvise.utils.error import FolderInPathTestCaseError
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


def rmfolder(name):
    assert 'cvise' in name
    try:
        shutil.rmtree(name)
    except OSError:
        pass


class TestEnvironment:
    def __init__(self, state, order, test_script, folder, test_case,
                 additional_files, transform, pid_queue=None):
        self.test_case = None
        self.additional_files = set()
        self.state = state
        self.folder = folder
        self.base_size = None
        self.test_script = test_script
        self.exitcode = None
        self.result = None
        self.order = order
        self.transform = transform
        self.pid_queue = pid_queue
        self.copy_files(test_case, additional_files)
        self.pwd = os.getcwd()

    def copy_files(self, test_case, additional_files):
        if test_case is not None:
            self.test_case = os.path.basename(test_case)
            shutil.copy(test_case, self.folder)
            self.base_size = os.path.getsize(test_case)

        for f in additional_files:
            self.additional_files.add(os.path.basename(f))
            shutil.copy(f, self.folder)

    @property
    def size_improvement(self):
        if self.base_size is None:
            return None
        else:
            return (self.base_size - os.path.getsize(self.test_case_path))

    @property
    def test_case_path(self):
        return os.path.join(self.folder, self.test_case)

    @property
    def additional_files_paths(self):
        return [os.path.join(self.folder, f) for f in self.additional_files]

    @property
    def success(self):
        return self.result == PassResult.OK and self.exitcode == 0

    def dump(self, dst):
        if self.test_case is not None:
            shutil.copy(self.test_case_path, dst)

        for f in self.additional_files:
            shutil.copy(f, dst)

        shutil.copy(self.test_script, dst)

    def run(self):
        try:
            # transform by state
            (result, self.state) = self.transform(self.test_case_path, self.state,
                                                  ProcessEventNotifier(self.pid_queue))
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
            stdout, stderr, returncode = ProcessEventNotifier(self.pid_queue).run_process(self.test_script, shell=True)
            if verbose and returncode != 0:
                logging.debug('stdout:\n' + stdout)
                logging.debug('stderr:\n' + stderr)
        finally:
            os.chdir(self.pwd)
        return returncode


class TestManager:
    GIVEUP_CONSTANT = 50000
    MAX_TIMEOUTS = 20
    MAX_CRASH_DIRS = 10
    MAX_EXTRA_DIRS = 25000
    TEMP_PREFIX = 'cvise-'

    def __init__(self, pass_statistic, test_script, timeout, save_temps, test_cases, parallel_tests,
                 no_cache, skip_key_off, silent_pass_bug, die_on_pass_bug, print_diff, max_improvement,
                 no_give_up, also_interesting, start_with_pass, skip_after_n_transforms):
        self.test_script = os.path.abspath(test_script)
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

        for test_case in test_cases:
            self.check_file_permissions(test_case, [os.F_OK, os.R_OK, os.W_OK], InvalidTestCaseError)
            if os.path.split(test_case)[0]:
                raise FolderInPathTestCaseError(test_case)
            fullpath = os.path.abspath(test_case)
            self.test_cases.add(fullpath)
            self.test_cases_modes[fullpath] = os.stat(fullpath).st_mode

        self.orig_total_file_size = self.total_file_size
        self.cache = {}
        self.root = None
        if not self.is_valid_test(self.test_script):
            raise InvalidInterestingnessTestError(self.test_script)

        self.use_colordiff = (sys.stdout.isatty() and
                              subprocess.run('colordiff --version', shell=True,
                                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0)

    def create_root(self):
        pass_name = str(self.current_pass).replace('::', '-')
        self.root = tempfile.mkdtemp(prefix=f'{self.TEMP_PREFIX}{pass_name}-')
        logging.debug('Creating pass root folder: %s' % self.root)

    def remove_root(self):
        if not self.save_temps:
            rmfolder(self.root)

    def restore_mode(self):
        for test_case in self.test_cases:
            os.chmod(test_case, self.test_cases_modes[test_case])

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
        return sorted(self.test_cases, key=os.path.getsize, reverse=True)

    @staticmethod
    def get_file_size(files):
        return sum(os.path.getsize(f) for f in files)

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
            orig_file = f'{f}.orig'

            if not os.path.exists(orig_file):
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
            extra_dir = ('{0}{1:0' + str(digits) + 'd}').format(prefix, i)

            if not os.path.exists(extra_dir):
                break

        # just bail if we've already created enough of these dirs, no need to
        # clutter things up even more...
        if os.path.exists(extra_dir):
            return None

        return extra_dir

    def report_pass_bug(self, test_env, problem):
        if not self.die_on_pass_bug:
            logging.warning(f'{self.current_pass} has encountered a non fatal bug: {problem}')

        crash_dir = self.get_extra_dir('cvise_bug_', self.MAX_CRASH_DIRS)

        if crash_dir is None:
            return

        os.mkdir(crash_dir)
        test_env.dump(crash_dir)

        if not self.die_on_pass_bug:
            logging.debug(f'Please consider tarring up {crash_dir} and creating an issue at https://github.com/marxin/cvise/issues and we will try to fix the bug.')

        with open(os.path.join(crash_dir, 'PASS_BUG_INFO.TXT'), mode='w') as info_file:
            info_file.write('Package: %s\n' % CVise.Info.PACKAGE_STRING)
            info_file.write('Git version: %s\n' % CVise.Info.GIT_VERSION)
            info_file.write('LLVM version: %s\n' % CVise.Info.LLVM_VERSION)
            info_file.write('System: %s\n' % str(platform.uname()))
            info_file.write(PassBugError.MSG.format(self.current_pass, problem, test_env.state, crash_dir))

        if self.die_on_pass_bug:
            raise PassBugError(self.current_pass, problem, test_env.state, crash_dir)

    @staticmethod
    def diff_files(orig_file, changed_file):
        with open(orig_file) as f:
            orig_file_lines = f.readlines()

        with open(changed_file) as f:
            changed_file_lines = f.readlines()

        diffed_lines = difflib.unified_diff(orig_file_lines, changed_file_lines, orig_file, changed_file)

        return ''.join(diffed_lines)

    def check_sanity(self, verbose=False):
        logging.debug('perform sanity check... ')

        folder = tempfile.mkdtemp(prefix=f'{self.TEMP_PREFIX}sanity-')
        test_env = TestEnvironment(None, 0, self.test_script, folder, None, self.test_cases, None)
        logging.debug(f'sanity check tmpdir = {test_env.folder}')

        returncode = test_env.run_test(verbose)
        if returncode == 0:
            rmfolder(folder)
            logging.debug('sanity check successful')
        else:
            if not self.save_temps:
                rmfolder(folder)
            raise InsaneTestCaseError(self.test_cases, self.test_script)

    def release_folder(self, future):
        name = self.temporary_folders.pop(future)
        if not self.save_temps:
            rmfolder(name)

    def release_folders(self):
        for future in self.futures:
            self.release_folder(future)
        assert not self.temporary_folders

    @classmethod
    def log_key_event(cls, event):
        logging.info('****** %s ******' % event)

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
                        child.terminate()
                    except psutil.NoSuchProcess:
                        pass
            except psutil.NoSuchProcess:
                pass

    def release_future(self, future):
        self.futures.remove(future)
        self.release_folder(future)

    def save_extra_dir(self, test_case_path):
        extra_dir = self.get_extra_dir('cvise_extra_', self.MAX_EXTRA_DIRS)
        if extra_dir is not None:
            os.mkdir(extra_dir)
            shutil.move(test_case_path, extra_dir)
            logging.info(f'Created extra directory {extra_dir} for you to look at later')

    def process_done_futures(self):
        quit_loop = False
        new_futures = set()
        for future in self.futures:
            # all items after first successfull (or STOP) should be cancelled
            if quit_loop:
                future.cancel()
                continue

            if future.done():
                if future.exception():
                    if type(future.exception()) is TimeoutError:
                        self.timeout_count += 1
                        logging.warning('Test timed out.')
                        self.save_extra_dir(self.temporary_folders[future])
                        if self.timeout_count >= self.MAX_TIMEOUTS:
                            logging.warning('Maximum number of timeout were reached: %d' % self.MAX_TIMEOUTS)
                            quit_loop = True
                        continue
                    else:
                        raise future.exception()

                test_env = future.result()
                if test_env.success:
                    if (self.max_improvement is not None and
                            test_env.size_improvement > self.max_improvement):
                        logging.debug(f'Too large improvement: {test_env.size_improvement} B')
                    else:
                        # Report bug if transform did not change the file
                        if filecmp.cmp(self.current_test_case, test_env.test_case_path):
                            if not self.silent_pass_bug:
                                self.report_pass_bug(test_env, 'pass failed to modify the variant')
                        else:
                            quit_loop = True
                            new_futures.add(future)
                else:
                    self.pass_statistic.add_failure(self.current_pass)
                    if test_env.result == PassResult.OK:
                        assert test_env.exitcode
                        if (self.also_interesting is not None and
                                test_env.exitcode == self.also_interesting):
                            self.save_extra_dir(test_env.test_case_path)
                    elif test_env.result == PassResult.STOP:
                        quit_loop = True
                    elif test_env.result == PassResult.ERROR:
                        if not self.silent_pass_bug:
                            self.report_pass_bug(test_env, 'pass error')
                            quit_loop = True
                    if not self.no_give_up and test_env.order > self.GIVEUP_CONSTANT:
                        self.report_pass_bug(test_env, 'pass got stuck')
                        quit_loop = True
            else:
                new_futures.add(future)

        removed_futures = [f for f in self.futures if f not in new_futures]
        for f in removed_futures:
            self.release_future(f)

        return quit_loop

    def wait_for_first_success(self):
        for future in self.futures:
            try:
                test_env = future.result()
                if test_env.success:
                    return test_env
            except TimeoutError:
                pass
        return None

    @classmethod
    def terminate_all(cls, pool):
        pool.stop()
        pool.join()

    def run_parallel_tests(self):
        assert not self.futures
        assert not self.temporary_folders
        with pebble.ProcessPool(max_workers=self.parallel_tests) as pool:
            order = 1
            self.timeout_count = 0
            while self.state is not None:
                # do not create too many states
                if len(self.futures) >= self.parallel_tests:
                    wait(self.futures, return_when=FIRST_COMPLETED)

                quit_loop = self.process_done_futures()
                if quit_loop:
                    success = self.wait_for_first_success()
                    self.terminate_all(pool)
                    return success

                folder = tempfile.mkdtemp(prefix=self.TEMP_PREFIX, dir=self.root)
                test_env = TestEnvironment(self.state, order, self.test_script, folder,
                                           self.current_test_case, self.test_cases ^ {self.current_test_case},
                                           self.current_pass.transform, self.pid_queue)
                future = pool.schedule(test_env.run, timeout=self.timeout)
                self.temporary_folders[future] = folder
                self.futures.append(future)
                self.pass_statistic.add_executed(self.current_pass)
                order += 1
                state = self.current_pass.advance(self.current_test_case, self.state)
                # we are at the end of enumeration
                if state is None:
                    success = self.wait_for_first_success()
                    self.terminate_all(pool)
                    return success
                else:
                    self.state = state

    def run_pass(self, pass_):
        if self.start_with_pass:
            if self.start_with_pass == str(pass_):
                self.start_with_pass = None
            else:
                return

        self.current_pass = pass_
        self.futures = []
        self.temporary_folders = {}
        m = Manager()
        self.pid_queue = m.Queue()
        self.create_root()
        pass_key = repr(self.current_pass)

        logging.info(f'===< {self.current_pass} >===')

        if self.total_file_size == 0:
            raise ZeroSizeError(self.test_cases)

        self.pass_statistic.start(self.current_pass)
        if not self.skip_key_off:
            logger = KeyLogger()

        try:
            for test_case in self.sorted_test_cases:
                self.current_test_case = test_case
                starting_test_case_size = os.path.getsize(test_case)
                success_count = 0

                if self.get_file_size([test_case]) == 0:
                    continue

                if not self.no_cache:
                    with open(test_case, mode='rb+') as tmp_file:
                        test_case_before_pass = tmp_file.read()

                        if (pass_key in self.cache and
                                test_case_before_pass in self.cache[pass_key]):
                            tmp_file.seek(0)
                            tmp_file.truncate(0)
                            tmp_file.write(self.cache[pass_key][test_case_before_pass])
                            logging.info(f'cache hit for {test_case}')
                            continue

                # create initial state
                self.state = self.current_pass.new(self.current_test_case, self.check_sanity)
                self.skip = False

                while self.state is not None and not self.skip:
                    # Ignore more key presses after skip has been detected
                    if not self.skip_key_off and not self.skip:
                        key = logger.pressed_key()
                        if key == 's':
                            self.skip = True
                            self.log_key_event('skipping the rest of this pass')
                        elif key == 'd':
                            self.log_key_event('toggle print diff')
                            self.print_diff = not self.print_diff

                    success_env = self.run_parallel_tests()
                    self.kill_pid_queue()

                    if success_env:
                        self.process_result(success_env)
                        success_count += 1

                    # if the file increases significantly, bail out the current pass
                    test_case_size = os.path.getsize(self.current_test_case)
                    if test_case_size >= MAX_PASS_INCREASEMENT_THRESHOLD * starting_test_case_size:
                        logging.info(f'skipping the rest of the pass (huge file increasement '
                                     f'{MAX_PASS_INCREASEMENT_THRESHOLD * 100}%)')
                        break

                    self.release_folders()
                    self.futures.clear()
                    if not success_env:
                        break

                    # skip after N transformations if requested
                    if self.skip_after_n_transforms and success_count >= self.skip_after_n_transforms:
                        logging.info(f'skipping after {success_count} successful transformations')
                        break

                # Cache result of this pass
                if not self.no_cache:
                    with open(test_case, mode='rb') as tmp_file:
                        if pass_key not in self.cache:
                            self.cache[pass_key] = {}

                        self.cache[pass_key][test_case_before_pass] = tmp_file.read()

            self.restore_mode()
            self.pass_statistic.stop(self.current_pass)
            self.remove_root()
        except KeyboardInterrupt:
            logging.info('Exiting now ...')
            self.remove_root()
            sys.exit(1)

    def process_result(self, test_env):
        if self.print_diff:
            diff_str = self.diff_files(self.current_test_case, test_env.test_case_path)
            if self.use_colordiff:
                diff_str = subprocess.check_output('colordiff', shell=True, encoding='utf8', input=diff_str)
            logging.info(diff_str)

        try:
            shutil.copy(test_env.test_case_path, self.current_test_case)
        except FileNotFoundError:
            raise RuntimeError(f"Can't find {self.current_test_case} -- did your interestingness test move it?")

        self.state = self.current_pass.advance_on_success(test_env.test_case_path, test_env.state)
        self.pass_statistic.add_success(self.current_pass)

        pct = 100 - (self.total_file_size * 100.0 / self.orig_total_file_size)
        notes = []
        notes.append(f'{round(pct, 1)}%')
        notes.append(f'{self.total_file_size} bytes')
        if self.total_line_count:
            notes.append(f'{self.total_line_count} lines')
        if len(self.test_cases) > 1:
            notes.append(test_env.test_case)

        logging.info('(' + ', '.join(notes) + ')')

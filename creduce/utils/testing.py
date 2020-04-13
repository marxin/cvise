import asyncio
import difflib
import filecmp
import importlib.util
import logging
import math
import multiprocessing
import os
import os.path
import platform
import shutil
import signal
import subprocess
import sys
import tempfile
import weakref

import concurrent.futures
from concurrent.futures import wait, FIRST_COMPLETED, TimeoutError
from pebble import ProcessPool

from .. import CReduce
from creduce.passes.abstract import AbstractPass, PassResult

from . import compat
from . import readkey
from .error import InsaneTestCaseError
from .error import InvalidInterestingnessTestError
from .error import InvalidTestCaseError
from .error import PassBugError
from .error import ZeroSizeError

def rmfolder(name):
    assert 'creduce' in name
    try:
        shutil.rmtree(name)
    except OSError:
        pass

class TestEnvironment:
    def __init__(self, test_script, save_temps, order, folder):
        self.test_case = None
        self.additional_files = set()
        self.state = None
        self.folder = folder
        self.save_temps = save_temps
        self.base_size = None
        self.test_script = test_script
        self.exitcode = None
        self.result = None
        self.order = order

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

    def run_test(self):
        cmd = [self.test_script]
        if self.test_case is not None:
            cmd.append(self.test_case_path)
        cmd.extend(self.additional_files_paths)

        return subprocess.run(cmd, cwd=self.folder, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

class TestManager:
    GIVEUP_CONSTANT = 50000
    MAX_CRASH_DIRS = 10
    MAX_EXTRA_DIRS = 25000
    TEMP_PREFIX = "creduce-"

    def __init__(self, pass_statistic, test_script, timeout, save_temps, test_cases, parallel_tests,
            no_cache, skip_key_off, silent_pass_bug, die_on_pass_bug, print_diff, max_improvement,
            no_give_up, also_interesting):
        self.test_script = os.path.abspath(test_script)
        self.timeout = timeout
        self.save_temps = save_temps
        self.pass_statistic = pass_statistic
        self.test_cases = set()
        self.parallel_tests = parallel_tests
        self.no_cache = no_cache
        self.skip_key_off = skip_key_off
        self.silent_pass_bug = silent_pass_bug
        self.die_on_pass_bug = die_on_pass_bug
        self.print_diff = print_diff
        self.max_improvement = max_improvement
        self.no_give_up = no_give_up
        self.also_interesting = also_interesting

        for test_case in test_cases:
            self.check_file_permissions(test_case, [os.F_OK, os.R_OK, os.W_OK], InvalidTestCaseError)
            self.test_cases.add(os.path.abspath(test_case))

        self.orig_total_file_size = self.total_file_size
        self.cache = {}
        self.root = None

        if not self.is_valid_test(self.test_script):
            raise InvalidInterestingnessTestError(test)

    def create_root(self):
        self.root = tempfile.mkdtemp(prefix=self.TEMP_PREFIX)

    def remove_root(self):
        rmfolder(self.root)

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
        return sorted(self.test_cases, key=os.path.getsize)

    @staticmethod
    def get_file_size(files):
        return sum(os.path.getsize(f) for f in files)

    def backup_test_cases(self):
        for f in self.test_cases:
            orig_file = "{}.orig".format(os.path.splitext(f)[0])

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
            extra_dir = ("{0}{1:0" + str(digits) + "d}").format(prefix, i)

            if not os.path.exists(extra_dir):
                break

        # just bail if we've already created enough of these dirs, no need to
        # clutter things up even more...
        if os.path.exists(extra_dir):
            return None

        return extra_dir

    def report_pass_bug(self, test_env, problem):
        if not self.die_on_pass_bug:
            logging.warning("{} has encountered a non fatal bug: {}".format(self.current_pass, problem))

        crash_dir = self.get_extra_dir("creduce_bug_", self.MAX_CRASH_DIRS)

        if crash_dir == None:
            return

        os.mkdir(crash_dir)
        test_env.dump(crash_dir)

        if not self.die_on_pass_bug:
            logging.debug("Please consider tarring up {} and mailing it to creduce-bugs@flux.utah.edu and we will try to fix the bug.".format(crash_dir))

        with open(os.path.join(crash_dir, "PASS_BUG_INFO.TXT"), mode="w") as info_file:
            info_file.write("{}\n".format(CReduce.Info.PACKAGE_STRING))
            info_file.write("{}\n".format(CReduce.Info.GIT_VERSION))
            info_file.write("{}\n".format(platform.uname()))
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

        return "".join(diffed_lines)

    def check_sanity(self):
        logging.debug("perform sanity check... ")

        folder = tempfile.mkdtemp(prefix=self.TEMP_PREFIX)
        test_env = self.create_environment(0, folder)

        logging.debug("sanity check tmpdir = {}".format(test_env.folder))

        test_env.copy_files(None, self.test_cases)

        p = test_env.run_test()
        rmfolder(folder)
        if not p.returncode:
            logging.debug("sanity check successful")
        else:
            raise InsaneTestCaseError(self.test_cases, p.args)

    def create_environment(self, order, folder):
        return TestEnvironment(self.test_script, self.save_temps, order, folder)

    def create_and_run_test_env(self, state, order, folder):
        try:
            test_env = self.create_environment(order, folder)
            test_env.copy_files(self.current_test_case, self.test_cases ^ {self.current_test_case})
            test_env.state = state

            # transform by state
            (result, test_env.state) = self.current_pass.transform(test_env.test_case_path, test_env.state)
            test_env.result = result
            if test_env.result != PassResult.OK:
                return test_env

            # run test script
            p = test_env.run_test()
            test_env.exitcode = p.returncode
            return test_env
        except OSError as e:
            # this can happen when we clean up temporary files for cancelled processes
            pass
        except Exception as e:
            print('Should not happen: ' + str(e))

    @classmethod
    def release_folder(cls, future, temporary_folders):
        name = temporary_folders.pop(future)
        rmfolder(name)

    @classmethod
    def release_folders(cls, futures, temporary_folders):
        for future in futures:
            cls.release_folder(future, temporary_folders)
        assert not any(temporary_folders)

    @classmethod
    def log_key_event(cls, event):
        logging.info("****** %s  ******" % event)

    def process_done_futures(self, futures, temporary_folders):
        quit_loop = False
        new_futures = []
        for future in futures:
            # all items after first successfull (or STOP) should be cancelled
            if quit_loop:
                future.cancel()
                continue

            if future.exception():
                if type(future.exception()) is TimeoutError:
                    future.cancel()
                    logging.debug("Test timed out!")
                else:
                    raise future.exception()
            else:
                if future.done():
                    test_env = future.result()
                    if test_env.success:
                        if (self.max_improvement is not None and
                            test_env.size_improvement > self.max_improvement):
                            logging.debug("Too large improvement: {} B".format(test_env.size_improvement))
                        else:
                            # Report bug if transform did not change the file
                            if filecmp.cmp(self.current_test_case, test_env.test_case_path):
                                if not self.silent_pass_bug:
                                    self.report_pass_bug(test_env, "pass failed to modify the variant")
                            else:
                                quit_loop = True
                                new_futures.append(future)
                    else:
                        if test_env.result == PassResult.OK:
                            assert test_env.exitcode
                            if (self.also_interesting is not None and
                                test_env.exitcode == self.also_interesting):
                                extra_dir = self.get_extra_dir("creduce_extra_", self.MAX_EXTRA_DIRS)
                                if extra_dir != None:
                                    os.mkdir(extra_dir)
                                    shutil.move(test_env.test_case_path, extra_dir)
                                    logging.info("Created extra directory {} for you to look at later".format(extra_dir))
                        elif test_env.result == PassResult.STOP:
                            quit_loop = True
                        elif test_env.result == PassResult.ERROR:
                            if not self.silent_pass_bug:
                                self.report_pass_bug(test_env, "pass error")
                        else:
                            if not self.no_give_up and test_env.order > self.GIVEUP_CONSTANT:
                                self.report_pass_bug(test_env, "pass got stuck")
                                quit_loop = True
                else:
                    new_futures.append(future)

        new_futures_set = set(new_futures)
        for future in futures:
            if not future in new_futures_set:
                self.release_folder(future, temporary_folders)

        return (quit_loop, new_futures)

    def wait_for_first_success(self, futures):
        for future in futures:
            try:
                test_env = future.result()
                if test_env.success:
                    return test_env
            except TimeoutError:
                future.cancel()
        return None

    @classmethod
    def terminate_all(cls, pool):
        pool.stop()
        pool.join()

    def run_parallel_tests(self):
        with ProcessPool(max_workers=self.parallel_tests) as pool:
            futures = []
            temporary_folders = {}
            order = 1
            while self.state != None:
                # do not create too many states
                if len(futures) >= self.parallel_tests:
                    wait(futures, return_when=FIRST_COMPLETED)

                (quit_loop, futures) = self.process_done_futures(futures, temporary_folders)
                if quit_loop:
                    success = self.wait_for_first_success(futures)
                    self.terminate_all(pool)
                    return (success, futures, temporary_folders)

                folder = tempfile.mkdtemp(prefix=self.TEMP_PREFIX, dir=self.root)
                future = pool.schedule(self.create_and_run_test_env, [self.state, order, folder],
                        timeout=self.timeout)
                temporary_folders[future] = folder
                futures.append(future)
                order += 1
                state = self.current_pass.advance(self.current_test_case, self.state)
                # we are at the end of enumeration
                if state == None:
                    success = self.wait_for_first_success(futures)
                    self.terminate_all(pool)
                    return (success, futures, temporary_folders)
                else:
                    self.state = state

    def run_pass(self, pass_):
        self.current_pass = pass_
        self.futures = []
        self.create_root()
        pass_key = repr(self.current_pass)

        logging.info("===< {} >===".format(self.current_pass))

        if self.total_file_size == 0:
            raise ZeroSizeError(self.test_cases)

        if not self.skip_key_off:
            logger = readkey.KeyLogger()

        for test_case in self.test_cases:
            self.current_test_case = test_case

            if self.get_file_size([test_case]) == 0:
                continue

            if not self.no_cache:
                with open(test_case, mode="r+") as tmp_file:
                    test_case_before_pass = tmp_file.read()

                    if (pass_key in self.cache and
                        test_case_before_pass in self.cache[pass_key]):
                        tmp_file.seek(0)
                        tmp_file.truncate(0)
                        tmp_file.write(self.cache[pass_key][test_case_before_pass])
                        logging.info("cache hit for {}".format(test_case))
                        continue

            # create initial state
            self.state = self.current_pass.new(self.current_test_case)
            self.skip = False
            self.since_success = 0

            while self.state != None and not self.skip:
                # Ignore more key presses after skip has been detected
                if not self.skip_key_off and not self.skip:
                    key = logger.pressed_key()
                    if key == "s":
                        self.skip = True
                        self.log_key_event("skipping the rest of this pass")
                    elif key == "d":
                        self.log_key_event("toggle print diff")
                        self.print_diff = not self.print_diff

                success_env, futures, temporary_folders = self.run_parallel_tests()
                if not success_env:
                    self.remove_root()
                    break

                self.process_result(success_env)
                self.release_folders(futures, temporary_folders)

            # Cache result of this pass
            if not self.no_cache:
                with open(test_case, mode="r") as tmp_file:
                    if pass_key not in self.cache:
                        self.cache[pass_key] = {}

                    self.cache[pass_key][test_case_before_pass] = tmp_file.read()

        self.remove_root()

    def process_result(self, test_env):
        logging.debug("Process result")

        if self.print_diff:
            diff_str = self.diff_files(self.current_test_case, test_env.test_case_path)
            logging.info(diff_str)

        shutil.copy(test_env.test_case_path, self.current_test_case)

        self.state = self.current_pass.advance_on_success(test_env.test_case_path, test_env.state)
        self.since_success = 0
        self.pass_statistic.update(self.current_pass, success=True)

        pct = 100 - (self.total_file_size * 100.0 / self.orig_total_file_size)
        logging.info("({}%, {} bytes)".format(round(pct, 1), self.total_file_size))

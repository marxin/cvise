#!/usr/bin/env python3

import argparse
import datetime
import importlib.util
import logging
import os
import os.path
import platform
import shutil
import sys
import tempfile
import time

# If the cvise modules cannot be found
# add the known install location to the path
destdir = os.getenv('DESTDIR', '')
if importlib.util.find_spec('cvise') is None:
    sys.path.append('@CMAKE_INSTALL_FULL_DATADIR@')
    sys.path.append(destdir + '@CMAKE_INSTALL_FULL_DATADIR@')

import chardet  # noqa: E402
from cvise.cvise import CVise  # noqa: E402
from cvise.passes.abstract import AbstractPass  # noqa: E402
from cvise.utils import misc, statistics, testing  # noqa: E402
from cvise.utils.error import CViseError  # noqa: E402
from cvise.utils.error import MissingPassGroupsError  # noqa: E402
import psutil  # noqa: E402


class DeltaTimeFormatter(logging.Formatter):
    def format(self, record):  # noqa: A003
        record.delta = str(datetime.timedelta(seconds=int(record.relativeCreated / 1000)))
        # pad with one more zero
        if record.delta[1] == ':':
            record.delta = '0' + record.delta
        return super().format(record)


script_path = os.path.dirname(os.path.realpath(__file__))


def get_share_dir():

    # Test all known locations for the cvise directory
    share_dirs = [
        os.path.join('@CMAKE_INSTALL_FULL_DATADIR@', '@cvise_PACKAGE@'),
        destdir + os.path.join('@CMAKE_INSTALL_FULL_DATADIR@', '@cvise_PACKAGE@'),
        os.path.join(script_path, 'cvise')
    ]

    for d in share_dirs:
        if os.path.isdir(d):
            return d

    raise CViseError('Cannot find cvise module directory!')


def find_external_programs():
    programs = {
        'clang_delta': 'clang_delta',
        'clex': 'clex',
        'topformflat': 'delta',
        'unifdef': None,
        'gcov-dump': None
    }

    for prog, local_folder in programs.items():
        path = None
        if local_folder:
            local_folder = os.path.join(script_path, local_folder)
            if platform.system() == 'Windows':
                for configuration in ['Debug', 'Release']:
                    new_local_folder = os.path.join(local_folder, configuration)
                    if os.path.exists(new_local_folder):
                        local_folder = new_local_folder
                        break

            path = shutil.which(prog, path=local_folder)

            if not path:
                search = os.path.join('@CMAKE_INSTALL_FULL_LIBEXECDIR@', '@cvise_PACKAGE@')
                path = shutil.which(prog, path=search)
            if not path:
                search = destdir + os.path.join('@CMAKE_INSTALL_FULL_LIBEXECDIR@', '@cvise_PACKAGE@')
                path = shutil.which(prog, path=search)

        if not path:
            path = shutil.which(prog)

        if path is not None:
            programs[prog] = path

    # Special case for clang-format
    programs['clang-format'] = '@CLANG_FORMAT_PATH@'

    return programs


def get_pass_group_path(name):
    return os.path.join(get_share_dir(), 'pass_groups', name + '.json')


def get_available_pass_groups():
    pass_group_dir = os.path.join(get_share_dir(), 'pass_groups')

    if not os.path.isdir(pass_group_dir):
        raise MissingPassGroupsError()

    group_names = []

    for entry in os.listdir(pass_group_dir):
        path = os.path.join(pass_group_dir, entry)

        if not os.path.isfile(path):
            continue

        try:
            pass_group_dict = CVise.load_pass_group_file(path)
            CVise.parse_pass_group_dict(pass_group_dict, set(), None, None, None, None, None, None)
        except MissingPassGroupsError:
            logging.warning(f'Skipping file {path}. Not valid pass group.')
        else:
            (name, _) = os.path.splitext(entry)
            group_names.append(name)

    return group_names


def get_available_cores():
    try:
        # try to detect only physical cores, ignore HyperThreading
        # in order to speed up parallel execution
        core_count = psutil.cpu_count(logical=False)
        if not core_count:
            core_count = psutil.cpu_count(logical=True)
        # respect affinity
        try:
            affinity = len(psutil.Process().cpu_affinity())
            assert affinity >= 1
        except AttributeError:
            return core_count

        if core_count:
            core_count = min(core_count, affinity)
        else:
            core_count = affinity
        return core_count
    except NotImplementedError:
        return 1


EPILOG_TEXT = """
available shortcuts:
  S - skip execution of the current pass
  D - toggle --print-diff option

For bug reporting instructions, please use:
%s
""" % CVise.Info.PACKAGE_URL

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='C-Vise', formatter_class=argparse.RawDescriptionHelpFormatter, epilog=EPILOG_TEXT)
    parser.add_argument('--n', '-n', type=int, default=get_available_cores(), help='Number of cores to use; C-Vise tries to automatically pick a good setting but its choice may be too low or high for your situation')
    parser.add_argument('--tidy', action='store_true', help='Do not make a backup copy of each file to reduce as file.orig')
    parser.add_argument('--shaddap', action='store_true', help='Suppress output about non-fatal internal errors')
    parser.add_argument('--die-on-pass-bug', action='store_true', help='Terminate C-Vise if a pass encounters an otherwise non-fatal problem')
    parser.add_argument('--sllooww', action='store_true', help='Try harder to reduce, but perhaps take a long time to do so')
    parser.add_argument('--also-interesting', metavar='EXIT_CODE', type=int, help='A process exit code (somewhere in the range 64-113 would be usual) that, when returned by the interestingness test, will cause C-Vise to save a copy of the variant')
    parser.add_argument('--debug', action='store_true', help='Print debug information (alias for --log-level=DEBUG)')
    parser.add_argument('--log-level', type=str, choices=['INFO', 'DEBUG', 'WARNING', 'ERROR'], default='INFO', help='Define the verbosity of the logged events')
    parser.add_argument('--log-file', type=str, help='Log events into LOG_FILE instead of stderr. New events are appended to the end of the file')
    parser.add_argument('--no-give-up', action='store_true', help=f"Don't give up on a pass that hasn't made progress for {testing.TestManager.GIVEUP_CONSTANT} iterations")
    parser.add_argument('--print-diff', action='store_true', help='Show changes made by transformations, for debugging')
    parser.add_argument('--save-temps', action='store_true', help="Don't delete /tmp/cvise-xxxxxx directories on termination")
    parser.add_argument('--skip-initial-passes', action='store_true', help='Skip initial passes (useful if input is already partially reduced)')
    parser.add_argument('--skip-interestingness-test-check', '-s', action='store_true', help='Skip initial interestingness test check')
    parser.add_argument('--remove-pass', help='Remove all instances of the specified passes from the schedule (comma-separated)')
    parser.add_argument('--start-with-pass', help='Start with the specified pass')
    parser.add_argument('--no-timing', action='store_true', help='Do not print timestamps about reduction progress')
    parser.add_argument('--timestamp', action='store_true', help='Print timestamps instead of relative time from a reduction start')
    parser.add_argument('--timeout', type=int, nargs='?', default=300, help='Interestingness test timeout in seconds')
    parser.add_argument('--no-cache', action='store_true', help="Don't cache behavior of passes")
    parser.add_argument('--skip-key-off', action='store_true', help="Disable skipping the rest of the current pass when 's' is pressed")
    parser.add_argument('--max-improvement', metavar='BYTES', type=int, help='Largest improvement in file size from a single transformation that C-Vise should accept (useful only to slow C-Vise down)')
    passes_group = parser.add_mutually_exclusive_group()
    passes_group.add_argument('--pass-group', type=str, choices=get_available_pass_groups(), help='Set of passes used during the reduction')
    passes_group.add_argument('--pass-group-file', type=str, help='JSON file defining a custom pass group')
    parser.add_argument('--clang-delta-std', type=str, choices=['c++98', 'c++11', 'c++14', 'c++17', 'c++20', 'c++2b'], help='Specify clang_delta C++ standard, it can rapidly speed up all clang_delta passes')
    parser.add_argument('--clang-delta-preserve-routine', type=str, help='Preserve the given function in replace-function-def-with-decl clang delta pass')
    parser.add_argument('--not-c', action='store_true', help="Don't run passes that are specific to C and C++, use this mode for reducing other languages")
    parser.add_argument('--renaming', action='store_true', help='Enable all renaming passes (that are disabled by default)')
    parser.add_argument('--list-passes', action='store_true', help='Print all available passes and exit')
    parser.add_argument('--version', action='version', version=CVise.Info.PACKAGE_STRING + (' (%s)' % CVise.Info.GIT_VERSION if CVise.Info.GIT_VERSION != 'unknown' else ''))
    parser.add_argument('--commands', '-c', help='Use bash commands instead of an interestingness test case')
    parser.add_argument('--to-utf8', action='store_true', help='Convert any non-UTF-8 encoded input file to UTF-8')
    parser.add_argument('--skip-after-n-transforms', type=int, help='Skip each pass after N successful transformations')
    parser.add_argument('interestingness_test', metavar='INTERESTINGNESS_TEST', nargs='?', help='Executable to check interestingness of test cases')
    parser.add_argument('test_cases', metavar='TEST_CASE', nargs='+', help='Test cases')

    args = parser.parse_args()

    log_config = {}

    log_format = '%(levelname)s %(message)s'
    if not args.no_timing:
        if args.timestamp:
            log_format = '%(asctime)s ' + log_format
        else:
            log_format = '%(delta)s ' + log_format

    if args.debug:
        log_config['level'] = logging.DEBUG
    else:
        log_config['level'] = getattr(logging, args.log_level.upper())

    if args.log_file is not None:
        log_config['filename'] = args.log_file

    logging.basicConfig(**log_config)
    syslog = logging.StreamHandler()
    formatter = DeltaTimeFormatter(log_format)
    syslog.setFormatter(formatter)
    logging.getLogger().handlers = []
    logging.getLogger().addHandler(syslog)

    pass_options = set()

    if sys.platform == 'win32':
        pass_options.add(AbstractPass.Option.windows)

    if args.sllooww:
        pass_options.add(AbstractPass.Option.slow)

    if args.pass_group is not None:
        pass_group_file = get_pass_group_path(args.pass_group)
    elif args.pass_group_file is not None:
        pass_group_file = args.pass_group_file
    else:
        pass_group_file = get_pass_group_path('all')

    external_programs = find_external_programs()

    pass_group_dict = CVise.load_pass_group_file(pass_group_file)
    pass_group = CVise.parse_pass_group_dict(pass_group_dict, pass_options, external_programs,
                                             args.remove_pass, args.clang_delta_std,
                                             args.clang_delta_preserve_routine, args.not_c, args.renaming)
    if args.list_passes:
        logging.info('Available passes:')
        logging.info('INITIAL PASSES')
        for p in pass_group['first']:
            logging.info(str(p))
        logging.info('MAIN PASSES')
        for p in pass_group['main']:
            logging.info(str(p))
        logging.info('CLEANUP PASSES')
        for p in pass_group['last']:
            logging.info(str(p))

        sys.exit(0)
        logging.shutdown()

    pass_statistic = statistics.PassStatistic()

    if not args.interestingness_test and not args.commands:
        print('Either INTERESTINGNESS_TEST or --commands must be used!')
        exit(1)

    # shift interestingness_test if --commands is used
    if args.interestingness_test and args.commands:
        args.test_cases.insert(0, args.interestingness_test)
        args.interestingness_test = None

    if args.to_utf8:
        for test_case in args.test_cases:
            with open(test_case, 'rb') as fd:
                encoding = chardet.detect(fd.read())['encoding']
                if encoding not in ('ascii', 'utf-8'):
                    logging.info(f'Converting {test_case} file ({encoding} encoding) to UTF-8')
                    data = open(test_case, encoding=encoding).read()
                    with open(test_case, 'w') as w:
                        w.write(data)

    script = None
    if args.commands:
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.sh') as script:
            script.write('#!/bin/bash\n\n')
            script.write(args.commands + '\n')
        os.chmod(script.name, 0o744)
        logging.info('Using temporary interestingness test: %s' % script.name)
        args.interestingness_test = script.name

    test_manager = testing.TestManager(pass_statistic, args.interestingness_test, args.timeout,
                                       args.save_temps, args.test_cases, args.n, args.no_cache, args.skip_key_off, args.shaddap,
                                       args.die_on_pass_bug, args.print_diff, args.max_improvement, args.no_give_up, args.also_interesting,
                                       args.start_with_pass, args.skip_after_n_transforms)

    reducer = CVise(test_manager, args.skip_interestingness_test_check)

    reducer.tidy = args.tidy

    # Track runtime
    time_start = time.monotonic()

    try:
        reducer.reduce(pass_group, skip_initial=args.skip_initial_passes)
    except CViseError as err:
        time_stop = time.monotonic()
        print(err)
    else:
        time_stop = time.monotonic()
        print('===< PASS statistics >===')
        print('  %-54s %8s %8s %8s %8s %15s' % ('pass name', 'time (s)', 'time (%)', 'worked',
              'failed', 'total executed'))

        for pass_name, pass_data in pass_statistic.sorted_results:
            print('  %-54s %8.2f %8.2f %8d %8d %15d' % (pass_name, pass_data.total_seconds,
                  100.0 * pass_data.total_seconds / (time_stop - time_start),
                pass_data.worked, pass_data.failed, pass_data.totally_executed))
        print()

        if not args.no_timing:
            print(f'Runtime: {round((time_stop - time_start))} seconds')

        print('Reduced test-cases:\n')
        for test_case in sorted(test_manager.test_cases):
            if misc.is_readable_file(test_case):
                print(f'--- {test_case} ---')
                with open(test_case) as test_case_file:
                    print(test_case_file.read())
        if script:
            os.unlink(script.name)

    logging.shutdown()

#!/usr/bin/env python3

import argparse
from contextlib import nullcontext
import datetime
import importlib.util
from itertools import chain
import logging
import os
import os.path
from pathlib import Path
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
from cvise.utils import statistics, testing  # noqa: E402
from cvise.utils.error import CViseError  # noqa: E402
from cvise.utils.error import MissingPassGroupsError  # noqa: E402
from cvise.utils.externalprograms import find_external_programs  # noqa: E402
from cvise.utils.hint import apply_hints, load_hints  # noqa: E402
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
        os.path.join(script_path, '@cvise_SHARE_DIR_SUFFIX@'),
    ]

    for d in share_dirs:
        if os.path.isdir(d):
            return d

    raise CViseError('Cannot find cvise module directory!')


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


EPILOG_TEXT = f"""
available shortcuts:
  S - skip execution of the current pass
  D - toggle --print-diff option

For bug reporting instructions, please use:
{CVise.Info.PACKAGE_URL}
"""


def main():
    parser = argparse.ArgumentParser(
        description='C-Vise',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=EPILOG_TEXT,
    )
    parser.add_argument(
        '--action',
        choices=['reduce', 'apply-hints'],
        default='reduce',
        help='Action to perform ("reduce" by default)',
    )
    parser.add_argument(
        '--n',
        '-n',
        type=int,
        default=get_available_cores(),
        help='Number of cores to use; C-Vise tries to automatically pick a good setting but its choice may be too low or high for your situation',
    )
    parser.add_argument(
        '--tidy',
        action='store_true',
        help='Do not make a backup copy of each file to reduce as file.orig',
    )
    parser.add_argument(
        '--shaddap',
        action='store_true',
        help='Suppress output about non-fatal internal errors',
    )
    parser.add_argument(
        '--die-on-pass-bug',
        action='store_true',
        help='Terminate C-Vise if a pass encounters an otherwise non-fatal problem',
    )
    parser.add_argument(
        '--sllooww',
        action='store_true',
        help='Try harder to reduce, but perhaps take a long time to do so',
    )
    parser.add_argument(
        '--also-interesting',
        metavar='EXIT_CODE',
        type=int,
        help='A process exit code (somewhere in the range 64-113 would be usual) that, when returned by the interestingness test, will cause C-Vise to save a copy of the variant',
    )
    parser.add_argument(
        '--debug',
        action='store_true',
        help='Print debug information (alias for --log-level=DEBUG)',
    )
    parser.add_argument(
        '--log-level',
        type=str,
        choices=['INFO', 'DEBUG', 'WARNING', 'ERROR'],
        default='INFO',
        help='Define the verbosity of the logged events',
    )
    parser.add_argument(
        '--log-file',
        type=str,
        help='Log events into LOG_FILE instead of stderr. New events are appended to the end of the file',
    )
    parser.add_argument(
        '--no-give-up',
        action='store_true',
        help=f"Don't give up on a pass that hasn't made progress for {testing.TestManager.GIVEUP_CONSTANT} iterations",
    )
    parser.add_argument(
        '--print-diff',
        action='store_true',
        help='Show changes made by transformations, for debugging',
    )
    parser.add_argument(
        '--save-temps',
        action='store_true',
        help="Don't delete /tmp/cvise-xxxxxx directories on termination",
    )
    parser.add_argument(
        '--skip-initial-passes',
        action='store_true',
        help='Skip initial passes (useful if input is already partially reduced)',
    )
    parser.add_argument(
        '--skip-interestingness-test-check',
        '-s',
        action='store_true',
        help='Skip initial interestingness test check',
    )
    parser.add_argument(
        '--remove-pass',
        help='Remove all instances of the specified passes from the schedule (comma-separated)',
    )
    parser.add_argument('--start-with-pass', help='Start with the specified pass')
    parser.add_argument(
        '--no-timing',
        action='store_true',
        help='Do not print timestamps about reduction progress',
    )
    parser.add_argument(
        '--timestamp',
        action='store_true',
        help='Print timestamps instead of relative time from a reduction start',
    )
    parser.add_argument(
        '--timeout',
        type=int,
        nargs='?',
        default=300,
        help='Interestingness test timeout in seconds',
    )
    parser.add_argument('--no-cache', action='store_true', help="Don't cache behavior of passes")
    parser.add_argument(
        '--skip-key-off',
        action='store_true',
        help="Disable skipping the rest of the current pass when 's' is pressed",
    )
    parser.add_argument(
        '--max-improvement',
        metavar='BYTES',
        type=int,
        help='Largest improvement in file size from a single transformation that C-Vise should accept (useful only to slow C-Vise down)',
    )
    passes_group = parser.add_mutually_exclusive_group()
    passes_group.add_argument(
        '--pass-group',
        type=str,
        choices=get_available_pass_groups(),
        help='Set of passes used during the reduction',
    )
    passes_group.add_argument('--pass-group-file', type=str, help='JSON file defining a custom pass group')
    parser.add_argument(
        '--clang-delta-std',
        type=str,
        choices=['c++98', 'c++11', 'c++14', 'c++17', 'c++20', 'c++2b'],
        help='Specify clang_delta C++ standard, it can rapidly speed up all clang_delta passes',
    )
    parser.add_argument(
        '--clang-delta-preserve-routine',
        type=str,
        help='Preserve the given function in replace-function-def-with-decl clang delta pass',
    )
    parser.add_argument(
        '--not-c',
        action='store_true',
        help="Don't run passes that are specific to C and C++, use this mode for reducing other languages",
    )
    parser.add_argument(
        '--renaming',
        action='store_true',
        help='Enable all renaming passes (that are disabled by default)',
    )
    parser.add_argument('--list-passes', action='store_true', help='Print all available passes and exit')
    parser.add_argument(
        '--version',
        action='version',
        version=CVise.Info.PACKAGE_STRING
        + (f' ({CVise.Info.GIT_VERSION})' if CVise.Info.GIT_VERSION != 'unknown' else ''),
    )
    parser.add_argument(
        '--commands',
        '-c',
        help='Use shell commands instead of an interestingness test case',
    )
    parser.add_argument('--shell', default='bash', help='Use selected shell for the --commands option')
    parser.add_argument(
        '--to-utf8',
        action='store_true',
        help='Convert any non-UTF-8 encoded input file to UTF-8',
    )
    parser.add_argument(
        '--skip-after-n-transforms',
        type=int,
        help='Skip each pass after N successful transformations',
    )
    parser.add_argument(
        'interestingness_test',
        metavar='INTERESTINGNESS_TEST',
        nargs='?',
        help='Executable to check interestingness of test cases',
    )
    parser.add_argument('test_cases', metavar='TEST_CASE', nargs='+', help='Test cases')
    parser.add_argument(
        '--stopping-threshold',
        default=1.0,
        type=float,
        help='CVise will stop reducing a test case once it has reduced by this fraction of its original size.  Between 0.0 and 1.0.',
    )
    parser.add_argument(
        '--hints-file', help='Path to file containing reduction hints (used only for --action=apply-hints)'
    )
    parser.add_argument(
        '--hint-begin-index',
        type=int,
        help='Index of the first hint to apply; 0-based (used only for --action=apply-hints)',
    )
    parser.add_argument(
        '--hint-end-index',
        type=int,
        help='Index past the last hint to apply; 0-based (used only for --action=apply-hints)',
    )

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

    logging.getLogger().setLevel(log_config['level'])
    formatter = DeltaTimeFormatter(log_format)
    root_logger = logging.getLogger()

    if args.log_file is not None:
        file_handler = logging.FileHandler(args.log_file)
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)
    else:
        syslog = logging.StreamHandler()
        syslog.setFormatter(formatter)
        root_logger.addHandler(syslog)

    if args.action == 'reduce':
        do_reduce(args)
    elif args.action == 'apply-hints':
        do_apply_hints(args)
    else:
        logging.error('Unknown action to perform: {args.action}')

    logging.shutdown()


def do_reduce(args):
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
    pass_group = CVise.parse_pass_group_dict(
        pass_group_dict,
        pass_options,
        external_programs,
        args.remove_pass,
        args.clang_delta_std,
        args.clang_delta_preserve_routine,
        args.not_c,
        args.renaming,
    )
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

    pass_statistic = statistics.PassStatistic()

    if args.start_with_pass:
        pass_names = [str(p) for p in chain(*pass_group.values())]
        if args.start_with_pass not in pass_names:
            print(
                f'Cannot find pass called "{args.start_with_pass}". '
                'Please use --list-passes to get a list of available passes.'
            )
            sys.exit(1)

    if not args.interestingness_test and not args.commands:
        print('Either INTERESTINGNESS_TEST or --commands must be used!')
        sys.exit(1)

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
            script.write(f'#!/usr/bin/env {args.shell}\n\n')
            script.write(args.commands + '\n')
        os.chmod(script.name, 0o744)
        logging.info(f'Using temporary interestingness test: {script.name}')
        args.interestingness_test = script.name

    try:
        test_manager = testing.TestManager(
            pass_statistic,
            args.interestingness_test,
            args.timeout,
            args.save_temps,
            args.test_cases,
            args.n,
            args.no_cache,
            args.skip_key_off,
            args.shaddap,
            args.die_on_pass_bug,
            args.print_diff,
            args.max_improvement,
            args.no_give_up,
            args.also_interesting,
            args.start_with_pass,
            args.skip_after_n_transforms,
            args.stopping_threshold,
        )

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
            with open(args.log_file, 'ab') if args.log_file else nullcontext(sys.stderr.buffer) as fs:
                fs.write(b'===< PASS statistics >===\n')
                fs.write(
                    (
                        '  %-60s %8s %8s %8s %8s %15s\n'
                        % (
                            'pass name',
                            'time (s)',
                            'time (%)',
                            'worked',
                            'failed',
                            'total executed',
                        )
                    ).encode()
                )

                for pass_name, pass_data in pass_statistic.sorted_results:
                    fs.write(
                        (
                            '  %-60s %8.2f %8.2f %8d %8d %15d\n'
                            % (
                                pass_name,
                                pass_data.total_seconds,
                                100.0 * pass_data.total_seconds / (time_stop - time_start),
                                pass_data.worked,
                                pass_data.failed,
                                pass_data.totally_executed,
                            )
                        ).encode()
                    )
                fs.write(b'\n')

                if not args.no_timing:
                    fs.write(f'Runtime: {round(time_stop - time_start)} seconds\n'.encode())

                fs.write(b'Reduced test-cases:\n\n')
                for test_case in sorted(test_manager.test_cases):
                    fs.write(f'--- {test_case} ---\n'.encode())
                    with open(test_case, 'rb') as test_case_file:
                        fs.write(test_case_file.read())
                        fs.write(b'\n')
    finally:
        if script:
            os.unlink(script.name)


def do_apply_hints(args):
    if args.hints_file is None:
        sys.exit('--hints-file is mandatory for --action=apply-hints')
    if args.hint_begin_index is None:
        sys.exit('--hint-begin-index is mandatory for --action=apply-hints')
    if args.hint_end_index is None:
        sys.exit('--hint-end-index is mandatory for --action=apply-hints')
    if args.hint_begin_index >= args.hint_end_index:
        sys.exit('HINT_BEGIN_INDEX must be smaller than HINT_END_INDEX')
    if len(args.test_cases) > 1:
        sys.exit('exactly one TEST_CASE must be supplied')
    bundle = load_hints(Path(args.hints_file), args.hint_begin_index, args.hint_end_index)
    new_data, stats = apply_hints([bundle], Path(args.test_cases[0]))
    sys.stdout.buffer.write(new_data)


if __name__ == '__main__':
    main()

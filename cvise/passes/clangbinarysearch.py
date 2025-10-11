import logging
from pathlib import Path
import re
import subprocess
import time
from typing import Optional

from cvise.passes.abstract import AbstractPass, BinaryState, PassResult


class ClangBinarySearchPass(AbstractPass):
    def __init__(
        self,
        arg: str,
        external_programs: dict[str, Optional[str]],
        user_clang_delta_std: Optional[str] = None,
        clang_delta_preserve_routine: Optional[str] = None,
        **kwargs,
    ):
        super().__init__(
            arg=arg,
            external_programs=external_programs,
            user_clang_delta_std=user_clang_delta_std,
            clang_delta_preserve_routine=clang_delta_preserve_routine,
            **kwargs,
        )
        self._user_clang_delta_std = user_clang_delta_std
        self._clang_delta_preserve_routine = clang_delta_preserve_routine

    def check_prerequisites(self):
        return self.check_external_program('clang_delta')

    def detect_best_standard(self, test_case: Path, timeout):
        best = None
        best_count = -1
        for std in ('c++98', 'c++11', 'c++14', 'c++17', 'c++20', 'c++2b'):
            start = time.monotonic()
            instances = self.count_instances(test_case, std, timeout)
            took = time.monotonic() - start

            # prefer newer standard if the # of instances is equal
            if instances >= best_count:
                best = std
                best_count = instances
            logging.debug('available transformation opportunities for %s: %d, took: %.2f s' % (std, instances, took))
        logging.info('using C++ standard: %s with %d transformation opportunities' % (best, best_count))
        # Use the best standard option
        return best

    def new(self, test_case: Path, job_timeout, *args, **kwargs):
        if not self._user_clang_delta_std:
            std = self.detect_best_standard(test_case, job_timeout)
        else:
            std = self._user_clang_delta_std
        state = BinaryState.create(self.count_instances(test_case, std, job_timeout))
        return attach_clang_delta_std(state, std)

    def advance(self, test_case: Path, state):
        new_state = state.advance()
        return attach_clang_delta_std(new_state, state.clang_delta_std)

    def advance_on_success(self, test_case: Path, state, succeeded_state, *args, **kwargs):
        instances = succeeded_state.real_num_instances - succeeded_state.real_chunk()
        new_state = state.advance_on_success(instances)
        if new_state:
            new_state.real_num_instances = None
        return attach_clang_delta_std(new_state, state.clang_delta_std)

    def count_instances(self, test_case: Path, std, timeout):
        args = [
            self.external_programs['clang_delta'],
            f'--query-instances={self.arg}',
            f'--std={std}',
        ]
        if self._clang_delta_preserve_routine:
            args.append(f'--preserve-routine="{self._clang_delta_preserve_routine}"')
        cmd = args + [str(test_case)]

        try:
            proc = subprocess.run(cmd, text=True, capture_output=True, timeout=timeout)
        except subprocess.TimeoutExpired:
            logging.warning(f'clang_delta --query-instances (--std={std}) {timeout}s timeout reached')
            return 0
        except subprocess.SubprocessError as e:
            logging.warning(f'clang_delta --query-instances (--std={std}) failed: {e}')
            return 0

        if proc.returncode != 0:
            logging.warning(
                f'clang_delta --query-instances failed with exit code {proc.returncode}: {proc.stderr.strip()}'
            )

        m = re.match('Available transformation instances: ([0-9]+)$', proc.stdout)

        if m is None:
            return 0
        else:
            return int(m.group(1))

    def parse_stderr(self, state, stderr):
        for line in stderr.split(b'\n'):
            if line.startswith(b'Available transformation instances:'):
                real_num_instances = int(line.decode().split(':')[1])
                state.real_num_instances = real_num_instances
            elif line.startswith(b'Warning: number of transformation instances exceeded'):
                # TODO: report?
                pass

    def transform(self, test_case: Path, state, process_event_notifier, *args, **kwargs):
        logging.debug(f'TRANSFORM: {state}')

        args = [
            f'--transformation={self.arg}',
            f'--counter={state.index + 1}',
            f'--to-counter={state.end()}',
            '--warn-on-counter-out-of-bounds',
            '--report-instances-count',
        ]
        args.append(f'--std={state.clang_delta_std}')
        if self._clang_delta_preserve_routine:
            args.append(f'--preserve-routine="{self._clang_delta_preserve_routine}"')
        prog = self.external_programs['clang_delta']
        assert prog
        cmd = [prog] + args + [str(test_case)]
        logging.debug(' '.join(cmd))

        stdout, stderr, returncode = process_event_notifier.run_process(cmd)
        self.parse_stderr(state, stderr)
        if returncode == 0:
            test_case.write_bytes(stdout)
            return (PassResult.OK, state)
        else:
            return (
                PassResult.STOP if returncode == 255 else PassResult.ERROR,
                state,
            )


def attach_clang_delta_std(state, std):
    if state is None:
        return None
    state.clang_delta_std = std
    return state

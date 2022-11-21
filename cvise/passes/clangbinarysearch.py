import logging
import os
import re
import shutil
import subprocess
import tempfile
import time

from cvise.passes.abstract import AbstractPass, BinaryState, PassResult


class ClangBinarySearchPass(AbstractPass):
    def check_prerequisites(self):
        return self.check_external_program('clang_delta')

    def detect_best_standard(self, test_case):
        best = None
        best_count = -1
        for std in ('c++98', 'c++11', 'c++14', 'c++17', 'c++20', 'c++2b'):
            self.clang_delta_std = std
            start = time.monotonic()
            instances = self.count_instances(test_case)
            took = time.monotonic() - start

            # prefer newer standard if the # of instances is equal
            if instances >= best_count:
                best = std
                best_count = instances
            logging.debug('available transformation opportunities for %s: %d, took: %.2f s' % (std, instances, took))
        logging.info('using C++ standard: %s with %d transformation opportunities' % (best, best_count))
        # Use the best standard option
        self.clang_delta_std = best

    def new(self, test_case, _=None):
        if not self.user_clang_delta_std:
            self.detect_best_standard(test_case)
        else:
            self.clang_delta_std = self.user_clang_delta_std
        return BinaryState.create(self.count_instances(test_case))

    def advance(self, test_case, state):
        return state.advance()

    def advance_on_success(self, test_case, state):
        instances = state.real_num_instances - state.real_chunk()
        state = state.advance_on_success(instances)
        if state:
            state.real_num_instances = None
        return state

    def count_instances(self, test_case):
        args = [self.external_programs['clang_delta'], f'--query-instances={self.arg}']
        if self.clang_delta_std:
            args.append(f'--std={self.clang_delta_std}')
        if self.clang_delta_preserve_routine:
            args.append(f'--preserve-routine="{self.clang_delta_preserve_routine}"')
        cmd = args + [test_case]

        try:
            proc = subprocess.run(cmd, universal_newlines=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        except subprocess.SubprocessError as e:
            logging.warning(f'clang_delta --query-instances failed: {e}')
            return 0

        if proc.returncode != 0:
            logging.warning(f'clang_delta --query-instances failed with exit code {proc.returncode}: {proc.stderr.strip()}')

        m = re.match('Available transformation instances: ([0-9]+)$', proc.stdout)

        if m is None:
            return 0
        else:
            return int(m.group(1))

    def parse_stderr(self, state, stderr):
        for line in stderr.split('\n'):
            if line.startswith('Available transformation instances:'):
                real_num_instances = int(line.split(':')[1])
                state.real_num_instances = real_num_instances
            elif line.startswith('Warning: number of transformation instances exceeded'):
                # TODO: report?
                pass

    def transform(self, test_case, state, process_event_notifier):
        logging.debug(f'TRANSFORM: index = {state.index}, chunk = {state.chunk}, instances = {state.instances}')

        tmp = os.path.dirname(test_case)
        with tempfile.NamedTemporaryFile(mode='w', delete=False, dir=tmp) as tmp_file:
            args = [f'--transformation={self.arg}', f'--counter={state.index + 1}', f'--to-counter={state.end()}',
                    '--warn-on-counter-out-of-bounds', '--report-instances-count']
            if self.clang_delta_std:
                args.append(f'--std={self.clang_delta_std}')
            if self.clang_delta_preserve_routine:
                args.append(f'--preserve-routine="{self.clang_delta_preserve_routine}"')
            cmd = [self.external_programs['clang_delta']] + args + [test_case]
            logging.debug(' '.join(cmd))

            stdout, stderr, returncode = process_event_notifier.run_process(cmd)
            self.parse_stderr(state, stderr)
            tmp_file.write(stdout)
            if returncode == 0:
                shutil.move(tmp_file.name, test_case)
                return (PassResult.OK, state)
            else:
                os.unlink(tmp_file.name)
                return (PassResult.STOP if returncode == 255 else PassResult.ERROR, state)

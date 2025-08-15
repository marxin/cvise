import logging
from pathlib import Path

from cvise.passes.abstract import AbstractPass, PassResult


class ClangPass(AbstractPass):
    def __init__(self, arg=None, external_programs=None):
        super().__init__(arg, external_programs)
        # The actual value is set by the caller in cvise.py.
        self.user_clang_delta_std = None

    def check_prerequisites(self):
        return self.check_external_program('clang_delta')

    def new(self, test_case: Path, *args, **kwargs):
        return 1

    def advance(self, test_case: Path, state):
        return state + 1

    def advance_on_success(self, test_case: Path, state, *args, **kwargs):
        return state

    def transform(self, test_case: Path, state, process_event_notifier, *args, **kwargs):
        args = [
            self.external_programs['clang_delta'],
            f'--transformation={self.arg}',
            f'--counter={state}',
        ]
        if self.user_clang_delta_std:
            args.append(f'--std={self.user_clang_delta_std}')
        cmd = args + [str(test_case)]

        logging.debug(' '.join(cmd))

        stdout, _, returncode = process_event_notifier.run_process(cmd)
        if returncode == 0:
            test_case.write_bytes(stdout)
            return (PassResult.OK, state)
        else:
            if returncode == 255 or returncode == 1:
                return (PassResult.STOP, state)
            else:
                return (PassResult.ERROR, state)

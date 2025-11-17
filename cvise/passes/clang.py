import logging
from pathlib import Path
from typing import Optional

from cvise.passes.abstract import AbstractPass, PassResult


class ClangPass(AbstractPass):
    def __init__(
        self,
        arg: str,
        external_programs: dict[str, Optional[str]],
        user_clang_delta_std: Optional[str] = None,
        **kwargs,
    ):
        super().__init__(
            arg=arg, external_programs=external_programs, user_clang_delta_std=user_clang_delta_std, **kwargs
        )
        self._user_clang_delta_std = user_clang_delta_std

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
        if self._user_clang_delta_std:
            args.append(f'--std={self._user_clang_delta_std}')
        cmd = args + [str(test_case)]

        logging.debug(' '.join(cmd))

        stdout, _, returncode = process_event_notifier.run_process(cmd)
        match returncode:
            case 0:
                test_case.write_bytes(stdout)
                return (PassResult.OK, state)
            case 1 | 255:
                return (PassResult.STOP, state)
            case _:
                return (PassResult.ERROR, state)

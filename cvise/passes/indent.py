from pathlib import Path
from typing import Dict, Optional

from cvise.passes.abstract import AbstractPass, PassResult
from cvise.utils.error import UnknownArgumentError


class IndentPass(AbstractPass):
    def __init__(self, external_programs: Dict[str, Optional[str]], **kwargs):
        super().__init__(external_programs=external_programs, **kwargs)

    def check_prerequisites(self):
        return self.check_external_program('clang-format')

    def new(self, test_case: Path, *args, **kwargs):
        return 0

    def advance(self, test_case: Path, state):
        return state + 1

    def advance_on_success(self, test_case: Path, state, *args, **kwargs):
        return state + 1

    def transform(self, test_case: Path, state, process_event_notifier, *args, **kwargs):
        if state != 0:
            return (PassResult.STOP, state)

        old = test_case.read_text()
        cmd = [self.external_programs['clang-format'], '-i']

        if self.arg == 'regular':
            cmd.extend(['-style', '{SpacesInAngles: true}', str(test_case)])
        elif self.arg == 'final':
            cmd.append(str(test_case))
        else:
            raise UnknownArgumentError(self.__class__.__name__, self.arg)

        _, _, returncode = process_event_notifier.run_process(cmd)
        if returncode != 0:
            return (PassResult.ERROR, state)

        new = test_case.read_text()
        if old == new:
            return (PassResult.STOP, state)
        else:
            return (PassResult.OK, state)

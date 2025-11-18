from pathlib import Path

from cvise.passes.abstract import AbstractPass, PassResult
from cvise.utils.error import UnknownArgumentError


class IndentPass(AbstractPass):
    def __init__(self, external_programs: dict[str, str | None], **kwargs):
        super().__init__(external_programs=external_programs, **kwargs)

    def check_prerequisites(self):
        return self.check_external_program('clang-format')

    def new(self, test_case: Path, *args, **kwargs):
        return 0

    def advance(self, test_case: Path, state):
        return None

    def advance_on_success(self, test_case: Path, state, *args, **kwargs):
        return None

    def transform(self, test_case: Path, state, process_event_notifier, *args, **kwargs):
        assert state == 0

        old = test_case.read_text()
        cmd = [self.external_programs['clang-format'], '-i']

        match self.arg:
            case 'regular':
                cmd.extend(['-style', '{SpacesInAngles: true}', str(test_case)])
            case 'final':
                cmd.append(str(test_case))
            case _:
                raise UnknownArgumentError(self.__class__.__name__, self.arg)

        _, _, returncode = process_event_notifier.run_process(cmd)
        if returncode != 0:
            return (PassResult.ERROR, state)

        new = test_case.read_text()
        if old == new:
            return (PassResult.STOP, state)
        else:
            return (PassResult.OK, state)

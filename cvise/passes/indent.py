from cvise.passes.abstract import AbstractPass, PassResult
from cvise.utils.error import UnknownArgumentError


class IndentPass(AbstractPass):
    def check_prerequisites(self):
        return self.check_external_program('clang-format')

    def new(self, test_case, _=None):
        return 0

    def advance(self, test_case, state):
        return state + 1

    def advance_on_success(self, test_case, state):
        return state + 1

    def transform(self, test_case, state, process_event_notifier):
        with open(test_case) as in_file:
            old = in_file.read()

        if state != 0:
            return (PassResult.STOP, state)

        cmd = [self.external_programs['clang-format'], '-i']

        if self.arg == 'regular':
            cmd.extend(['-style', '{SpacesInAngles: true}', test_case])
        elif self.arg == 'final':
            cmd.append(test_case)
        else:
            raise UnknownArgumentError(self.__class__.__name__, self.arg)

        _, _, returncode = process_event_notifier.run_process(cmd)
        if returncode != 0:
            return (PassResult.ERROR, state)

        with open(test_case) as in_file:
            new = in_file.read()

        if old == new:
            return (PassResult.STOP, state)
        else:
            return (PassResult.OK, state)

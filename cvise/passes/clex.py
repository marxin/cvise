from pathlib import Path

from cvise.passes.abstract import AbstractPass, PassResult


class ClexPass(AbstractPass):
    def check_prerequisites(self):
        return self.check_external_program('clex')

    def new(self, test_case: Path, *args, **kwargs):
        return 0

    def advance(self, test_case: Path, state):
        return state + 1

    def advance_on_success(self, test_case: Path, state, *args, **kwargs):
        return state

    def transform(self, test_case: Path, state, process_event_notifier):
        cmd = [self.external_programs['clex'], str(self.arg), str(state), str(test_case)]
        stdout, _stderr, returncode = process_event_notifier.run_process(cmd)
        if returncode == 51:
            test_case.write_bytes(stdout)
            return (PassResult.OK, state)
        else:
            return (
                PassResult.STOP if returncode == 71 else PassResult.ERROR,
                state,
            )

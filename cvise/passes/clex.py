import os
import shutil
import tempfile

from cvise.passes.abstract import AbstractPass, PassResult


class ClexPass(AbstractPass):
    def check_prerequisites(self):
        return self.check_external_program('clex')

    def new(self, test_case, _=None):
        return 0

    def advance(self, test_case, state):
        return state + 1

    def advance_on_success(self, test_case, state):
        return state

    def transform(self, test_case, state, process_event_notifier):
        tmp = os.path.dirname(test_case)
        with tempfile.NamedTemporaryFile(mode='w', delete=False, dir=tmp) as tmp_file:
            cmd = [self.external_programs['clex'], str(self.arg), str(state), test_case]
            stdout, stderr, returncode = process_event_notifier.run_process(cmd)
            if returncode == 51:
                tmp_file.write(stdout)
                shutil.move(tmp_file.name, test_case)
                return (PassResult.OK, state)
            else:
                os.unlink(tmp_file.name)
                return (
                    PassResult.STOP if returncode == 71 else PassResult.ERROR,
                    state,
                )

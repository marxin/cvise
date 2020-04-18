import os
import shutil
import subprocess
import tempfile

from cvise.passes.abstract import AbstractPass, PassResult
from cvise.utils import compat

class ClexPass(AbstractPass):
    def check_prerequisites(self):
        return shutil.which(self.external_programs["clex"]) is not None

    def new(self, test_case):
        return 0

    def advance(self, test_case, state):
        return state + 1

    def advance_on_success(self, test_case, state):
        return state

    def transform(self, test_case, state):
        tmp = os.path.dirname(test_case)
        with tempfile.NamedTemporaryFile(mode="w+", delete=False, dir=tmp) as tmp_file:
            cmd = [self.external_programs["clex"], str(self.arg), str(state), test_case]

            try:
                proc = compat.subprocess_run(cmd, universal_newlines=True, stdout=tmp_file, stderr=subprocess.PIPE)
            except subprocess.SubprocessError:
                return (PassResult.ERROR, state)

        if proc.returncode == 51:
            shutil.move(tmp_file.name, test_case)
            return (PassResult.OK, state)
        else:
            os.unlink(tmp_file.name)
            return (PassResult.STOP if proc.returncode == 71 else PassResult.ERROR, state)

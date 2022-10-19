import filecmp
import os
import shutil
import subprocess
import tempfile

from cvise.passes.abstract import AbstractPass, PassResult


class UnIfDefPass(AbstractPass):
    def check_prerequisites(self):
        return self.check_external_program('unifdef')

    def new(self, test_case, _=None):
        return 0

    def advance(self, test_case, state):
        return state + 1

    def advance_on_success(self, test_case, state):
        return state

    def transform(self, test_case, state, process_event_notifier):
        try:
            cmd = [self.external_programs['unifdef'], '-s', test_case]
            proc = subprocess.run(cmd, universal_newlines=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        except subprocess.SubprocessError:
            return (PassResult.ERROR, state)

        defs = {}

        for line in proc.stdout.splitlines():
            defs[line] = 1

        deflist = sorted(defs.keys())

        tmp = os.path.dirname(test_case)
        with tempfile.NamedTemporaryFile(mode='w+', delete=False, dir=tmp) as tmp_file:
            while True:
                du = '-D' if state % 2 == 0 else '-U'
                n_index = int(state / 2)

                if n_index >= len(deflist):
                    os.unlink(tmp_file.name)
                    return (PassResult.STOP, state)

                def_ = deflist[n_index]

                cmd = [self.external_programs['unifdef'], '-B', '-x', '2', f'{du}{def_}', '-o', tmp_file.name, test_case]
                stdout, stderr, returncode = process_event_notifier.run_process(cmd)
                if returncode != 0:
                    return (PassResult.ERROR, state)

                if filecmp.cmp(test_case, tmp_file.name, shallow=False):
                    state += 1
                    continue

                shutil.move(tmp_file.name, test_case)
                return (PassResult.OK, state)

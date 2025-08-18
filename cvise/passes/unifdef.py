import filecmp
from pathlib import Path
import shutil
import subprocess
import tempfile

from cvise.passes.abstract import AbstractPass, PassResult


class UnIfDefPass(AbstractPass):
    def check_prerequisites(self):
        return self.check_external_program('unifdef')

    def new(self, test_case: Path, *args, **kwargs):
        return 0

    def advance(self, test_case: Path, state):
        return state + 1

    def advance_on_success(self, test_case: Path, state, *args, **kwargs):
        return state

    def transform(self, test_case: Path, state, process_event_notifier, *args, **kwargs):
        try:
            cmd = [self.external_programs['unifdef'], '-s', str(test_case)]
            proc = subprocess.run(cmd, text=True, capture_output=True)
        except subprocess.SubprocessError:
            return (PassResult.ERROR, state)

        defs = {}

        for line in proc.stdout.splitlines():
            defs[line] = 1

        deflist = sorted(defs.keys())

        with tempfile.NamedTemporaryFile(mode='w+', delete=False, dir=test_case.parent) as tmp_file:
            tmp_path = Path(tmp_file.name)
            tmp_file.close()
            while True:
                du = '-D' if state % 2 == 0 else '-U'
                n_index = int(state / 2)

                if n_index >= len(deflist):
                    tmp_path.unlink()
                    return (PassResult.STOP, state)

                def_ = deflist[n_index]

                cmd = [
                    self.external_programs['unifdef'],
                    '-B',
                    '-x',
                    '2',
                    f'{du}{def_}',
                    '-o',
                    tmp_file.name,
                    str(test_case),
                ]
                _stdout, _stderr, returncode = process_event_notifier.run_process(cmd)
                if returncode != 0:
                    return (PassResult.ERROR, state)

                if filecmp.cmp(test_case, tmp_path, shallow=False):
                    state += 1
                    continue

                shutil.move(tmp_path, test_case)
                return (PassResult.OK, state)

import json
import subprocess

from cvise.passes.hint_based import HintBasedPass
from cvise.utils.hint import GROUPING_ONEBYONE, HintBundle


class ClexHintsPass(HintBasedPass):
    """A pass for removing tokens based on the hints from the "clex" tool."""

    def check_prerequisites(self):
        return self.check_external_program('clex')

    def generate_hints(self, test_case):
        assert 'hints' in self.arg
        hints = []
        cmd = [self.external_programs['clex'], self.arg, '-1', str(test_case)]
        with subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE) as proc:
            vocab = json.loads(next(proc.stdout))
            for line in proc.stdout:
                if not line.isspace():
                    hints.append(json.loads(line))
        return HintBundle(vocabulary=vocab, hints=hints, grouping=GROUPING_ONEBYONE)

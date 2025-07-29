import json
import subprocess

from cvise.passes.abstract import SubsegmentState
from cvise.passes.hint_based import HintBasedPass
from cvise.utils.hint import HintBundle


class ClexHintsPass(HintBasedPass):
    """A pass for removing tokens based on the hints from the "clex" tool."""

    def check_prerequisites(self):
        return self.check_external_program('clex')

    def generate_hints(self, test_case):
        if self.arg.startswith('rm-toks-'):
            clex_cmd = 'hints-rm-toks'
        else:
            raise ValueError(f'Unexpected arg: {self.arg}')
        tok_index = '-1'  # unused
        cmd = [self.external_programs['clex'], clex_cmd, tok_index, str(test_case)]
        hints = []
        with subprocess.Popen(cmd, stdout=subprocess.PIPE) as proc:
            vocab = json.loads(next(proc.stdout))
            for line in proc.stdout:
                if not line.isspace():
                    hints.append(json.loads(line))
        return HintBundle(vocabulary=vocab, hints=hints)

    def create_elementary_state(self, hint_count: int):
        if self.arg.startswith('rm-toks-'):
            max_chunk = int(self.arg[len('rm-toks-') :])
            return SubsegmentState(instances=hint_count, index=0, chunk=max_chunk)
        raise ValueError(f'Unexpected arg: {self.arg}')

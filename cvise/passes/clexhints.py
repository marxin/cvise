import msgspec
import re
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
            # Note that we don't pass the number of tokens to the parser - its job is just to find each token's
            # boundaries; the number is used for constructing the SubsegmentState instead.
            clex_cmd = 'hints-toks'
        else:
            raise ValueError(f'Unexpected arg: {self.arg}')
        tok_index = '-1'  # unused
        cmd = [self.external_programs['clex'], clex_cmd, tok_index, str(test_case)]
        hints = []
        decoder = msgspec.json.Decoder()
        with subprocess.Popen(cmd, stdout=subprocess.PIPE) as proc:
            vocab = decoder.decode(next(proc.stdout))
            for line in proc.stdout:
                if not line.isspace():
                    hints.append(decoder.decode(line))
        return HintBundle(vocabulary=vocab, hints=hints)

    def create_elementary_state(self, hint_count: int):
        m = re.fullmatch(r'rm-toks-(\d+)-to-(\d+)', self.arg)
        if m:
            min_chunk = int(m.group(1))
            max_chunk = int(m.group(2))
            return SubsegmentState.create(instances=hint_count, min_chunk=min_chunk, max_chunk=max_chunk)
        raise ValueError(f'Unexpected arg: {self.arg}')

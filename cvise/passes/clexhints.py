import msgspec
from pathlib import Path
import re

from cvise.passes.abstract import SubsegmentState
from cvise.passes.hint_based import HintBasedPass
from cvise.utils.hint import HintBundle
from cvise.utils.process import ProcessEventNotifier


class ClexHintsPass(HintBasedPass):
    """A pass for removing tokens based on the hints from the "clex" tool."""

    def check_prerequisites(self):
        return self.check_external_program('clex')

    def generate_hints(self, test_case: Path, process_event_notifier: ProcessEventNotifier, *args, **kwargs):
        if self.arg.startswith('rm-toks-'):
            # Note that we don't pass the number of tokens to the parser - its job is just to find each token's
            # boundaries; the number is used for constructing the SubsegmentState instead.
            clex_cmd = 'hints-toks'
        else:
            raise ValueError(f'Unexpected arg: {self.arg}')
        tok_index = '-1'  # unused
        cmd = [self.external_programs['clex'], clex_cmd, tok_index, str(test_case)]
        stdout, _stderr, _returncode = process_event_notifier.run_process(cmd)
        hints = []
        decoder = msgspec.json.Decoder()
        stdout = iter(stdout.splitlines())
        vocab = decoder.decode(next(stdout))
        for line in stdout:
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

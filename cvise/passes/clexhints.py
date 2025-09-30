import msgspec
from pathlib import Path
import re
import subprocess
from typing import List

from cvise.passes.abstract import SubsegmentState
from cvise.passes.hint_based import HintBasedPass
from cvise.utils.hint import Hint, HintBundle
from cvise.utils.process import ProcessEventNotifier


class ClexHintsPass(HintBasedPass):
    """A pass for removing tokens based on the hints from the "clex" tool."""

    def check_prerequisites(self):
        return self.check_external_program('clex')

    def supports_dir_test_cases(self):
        return True

    def generate_hints(self, test_case: Path, process_event_notifier: ProcessEventNotifier, *args, **kwargs):
        if self.arg.startswith('rm-toks-'):
            # Note that we don't pass the number of tokens to the parser - its job is just to find each token's
            # boundaries; the number is used for constructing the SubsegmentState instead.
            clex_cmd = 'hints-toks'
        else:
            raise ValueError(f'Unexpected arg: {self.arg}')
        tok_index = '-1'  # unused

        # If the test case is a single file, simply specify its path via cmd line. If it's a directory, enumerate all
        # files (we do it on the Python side for flexibility) and send the list via stdin (to not hit the cmd line size
        # limit).
        if test_case.is_dir():
            work_dir = test_case
            paths = [p.relative_to(test_case) for p in test_case.rglob('*') if not p.is_dir()]
            stdin = b'\0'.join(bytes(p) for p in paths)
            files_vocab = [str(p).encode() for p in paths]
            cmd_arg = '--'
        else:
            work_dir = None
            stdin = b''
            files_vocab = []
            cmd_arg = str(test_case)

        cmd = [self.external_programs['clex'], clex_cmd, tok_index, cmd_arg]
        stdout, _stderr, _returncode = process_event_notifier.run_process(
            cmd, cwd=work_dir, stdin=subprocess.PIPE, input=stdin
        )

        # When reading, gracefully handle EOF because the tool might've failed with no output.
        stdout = iter(stdout.splitlines())
        vocab_line = next(stdout, None)
        vocab_decoder = msgspec.json.Decoder(type=List[str])
        orig_vocab = [s.encode() for s in vocab_decoder.decode(vocab_line)] if vocab_line else []

        hints = []
        hint_decoder = msgspec.json.Decoder(type=Hint)
        for line in stdout:
            if not line.isspace():
                hint = hint_decoder.decode(line)
                # Shift file identifiers according to their position in the vocabulary.
                new_patches = tuple(
                    msgspec.structs.replace(p, file=None if p.file is None else p.file + len(orig_vocab))
                    for p in hint.patches
                )
                new_hint = msgspec.structs.replace(hint, patches=new_patches)
                hints.append(new_hint)
        return HintBundle(vocabulary=orig_vocab + files_vocab, hints=hints)

    def create_elementary_state(self, hint_count: int):
        m = re.fullmatch(r'rm-toks-(\d+)-to-(\d+)', self.arg)
        if m:
            min_chunk = int(m.group(1))
            max_chunk = int(m.group(2))
            return SubsegmentState.create(instances=hint_count, min_chunk=min_chunk, max_chunk=max_chunk)
        raise ValueError(f'Unexpected arg: {self.arg}')

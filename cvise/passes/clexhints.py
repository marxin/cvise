import msgspec
from pathlib import Path
import re
import subprocess
from typing import Optional

from cvise.passes.abstract import SubsegmentState
from cvise.passes.hint_based import HintBasedPass
from cvise.utils.fileutil import filter_files_by_patterns
from cvise.utils.hint import Hint, HintBundle
from cvise.utils.process import ProcessEventNotifier


class ClexHintsPass(HintBasedPass):
    """A pass for removing tokens based on the hints from the "clex" tool."""

    def __init__(self, arg: str, external_programs: dict[str, Optional[str]], **kwargs):
        super().__init__(arg=arg, external_programs=external_programs, **kwargs)

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
        paths = filter_files_by_patterns(test_case, self.claim_files, self.claimed_by_others_files)
        if not paths:
            return HintBundle(hints=[])
        if test_case.is_dir():
            work_dir = test_case
            rel_paths = [p.relative_to(test_case) for p in paths]
            files_vocab = [str(p).encode() for p in rel_paths]  # avoid the complexity of escaping paths in C code
            stdin = b'\0'.join(files_vocab)
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
        vocab_decoder = msgspec.json.Decoder(type=list[str])
        orig_vocab = [s.encode() for s in vocab_decoder.decode(vocab_line)] if vocab_line else []

        hints = []
        hint_decoder = msgspec.json.Decoder(type=Hint)
        for line in stdout:
            if not line.isspace():
                hint = hint_decoder.decode(line)
                # Shift file identifiers according to their position in the vocabulary.
                new_patches = tuple(
                    msgspec.structs.replace(p, path=None if p.path is None else p.path + len(orig_vocab))
                    for p in hint.patches
                )
                new_hint = msgspec.structs.replace(hint, patches=new_patches)
                hints.append(new_hint)
        return HintBundle(vocabulary=orig_vocab + files_vocab, hints=hints)

    def create_elementary_state(self, hint_count: int):
        assert self.arg is not None
        m = re.fullmatch(r'rm-toks-(\d+)-to-(\d+)', self.arg)
        if m:
            min_chunk = int(m.group(1))
            max_chunk = int(m.group(2))
            return SubsegmentState.create(instances=hint_count, min_chunk=min_chunk, max_chunk=max_chunk)
        raise ValueError(f'Unexpected arg: {self.arg}')

import msgspec
from pathlib import Path
import subprocess
from typing import List

from cvise.passes.hint_based import HintBasedPass
from cvise.utils.hint import Hint, HintBundle
from cvise.utils.process import ProcessEventNotifier


class TreeSitterPass(HintBasedPass):
    """A pass that performs reduction using heuristics based on the Tree-sitter parser (via treesitter_delta tool)."""

    def check_prerequisites(self):
        return self.check_external_program('treesitter_delta')

    def supports_dir_test_cases(self):
        return True

    def output_hint_types(self) -> List[bytes]:
        # Must stay in sync with the heuristic implementations in //treesitter_delta/.
        if self.arg == 'replace-function-def-with-decl':
            return [b'regular', b'template-function']
        else:
            return []

    def generate_hints(self, test_case: Path, process_event_notifier: ProcessEventNotifier, *args, **kwargs):
        # If the test case is a single file, simply specify its path via cmd line. If it's a directory, enumerate all
        # files (we do it on the Python side for flexibility) and send the list via stdin (to not hit the cmd line size
        # limit).
        if test_case.is_dir():
            work_dir = test_case
            paths = [p.relative_to(test_case) for p in test_case.rglob('*') if not p.is_dir()]
            stdin = b'\0'.join(bytes(p) for p in paths)
            cmd_arg = '--'
        else:
            work_dir = None
            paths = []
            stdin = b''
            cmd_arg = str(test_case)

        cmd = [self.external_programs['treesitter_delta'], self.arg, cmd_arg]
        stdout = process_event_notifier.check_output(cmd, cwd=work_dir, stdin=subprocess.PIPE, input=stdin)

        # When reading, gracefully handle EOF because the tool might've failed with no output.
        stdout = iter(stdout.splitlines())
        vocab_line = next(stdout, None)
        vocab_decoder = msgspec.json.Decoder(type=List[str])
        vocab = [s.encode() for s in vocab_decoder.decode(vocab_line)] if vocab_line else []
        vocab += [str(p).encode() for p in paths]  # input paths aren't printed by the tool, due to escaping complexity

        hints = []
        hint_decoder = msgspec.json.Decoder(type=Hint)
        for line in stdout:
            if not line.isspace():
                hints.append(hint_decoder.decode(line))
        return HintBundle(vocabulary=vocab, hints=hints)

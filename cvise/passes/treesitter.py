import msgspec
from pathlib import Path
import subprocess

from cvise.passes.hint_based import HintBasedPass
from cvise.utils.hint import HintBundle
from cvise.utils.process import ProcessEventNotifier


class TreeSitterPass(HintBasedPass):
    """A pass that performs reduction using heuristics based on the Tree-sitter parser (via treesitter_delta tool)."""

    def check_prerequisites(self):
        return self.check_external_program('treesitter_delta')

    def supports_dir_test_cases(self):
        return True

    def generate_hints(self, test_case: Path, process_event_notifier: ProcessEventNotifier, *args, **kwargs):
        # If the test case is a single file, simply specify its path via cmd line. If it's a directory, enumerate all
        # files (we do it on the Python side for flexibility) and send the list via stdin (to not hit the cmd line size
        # limit).
        if test_case.is_dir():
            work_dir = test_case
            paths = [p.relative_to(test_case) for p in test_case.rglob('*') if not p.is_dir()]
            stdin = b'\n'.join(bytes(p) for p in paths)
            cmd_arg = '--'
        else:
            work_dir = '.'
            stdin = b''
            cmd_arg = str(test_case)

        cmd = [self.external_programs['treesitter_delta'], self.arg, cmd_arg]
        stdout = process_event_notifier.check_output(cmd, cwd=work_dir, stdin=subprocess.PIPE, input=stdin, stderr=None)

        # When reading, gracefully handle EOF because the tool might've failed with no output.
        stdout = iter(stdout.splitlines())
        vocab_line = next(stdout, None)
        decoder = msgspec.json.Decoder()
        vocab = decoder.decode(vocab_line) if vocab_line else []

        hints = []
        for line in stdout:
            if not line.isspace():
                hints.append(decoder.decode(line))
        return HintBundle(vocabulary=vocab, hints=hints)

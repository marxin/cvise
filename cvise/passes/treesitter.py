import msgspec
from pathlib import Path
import subprocess

from cvise.passes.hint_based import HintBasedPass
from cvise.utils.hint import HintBundle


class TreeSitterPass(HintBasedPass):
    """A pass that performs reduction using heuristics based on the Tree-sitter parser (via treesitter_delta tool)."""

    def check_prerequisites(self):
        return self.check_external_program('treesitter_delta')

    def generate_hints(self, test_case: Path):
        cmd = [
            self.external_programs['treesitter_delta'],
            self.arg,
            str(test_case),
        ]
        proc = subprocess.run(cmd, text=True, capture_output=True)

        if proc.returncode != 0:
            stderr = proc.stderr.strip()
            delim = ': ' if stderr else ''
            raise RuntimeError(f'treesitter_delta failed with exit code {proc.returncode}{delim}{stderr}')

        # When reading, gracefully handle EOF because the tool might've failed with no output.
        stdout = iter(proc.stdout.splitlines())
        vocab_line = next(stdout, None)
        decoder = msgspec.json.Decoder()
        vocab = decoder.decode(vocab_line) if vocab_line else []

        hints = []
        for line in stdout:
            if not line.isspace():
                hints.append(decoder.decode(line))
        return HintBundle(vocabulary=vocab, hints=hints)

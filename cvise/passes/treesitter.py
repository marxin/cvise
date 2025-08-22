import msgspec
from pathlib import Path

from cvise.passes.hint_based import HintBasedPass
from cvise.utils.hint import HintBundle
from cvise.utils.process import ProcessEventNotifier


class TreeSitterPass(HintBasedPass):
    """A pass that performs reduction using heuristics based on the Tree-sitter parser (via treesitter_delta tool)."""

    def check_prerequisites(self):
        return self.check_external_program('treesitter_delta')

    def generate_hints(self, test_case: Path, process_event_notifier: ProcessEventNotifier, *args, **kwargs):
        cmd = [
            self.external_programs['treesitter_delta'],
            self.arg,
            str(test_case),
        ]
        stdout = process_event_notifier.check_output(cmd)

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

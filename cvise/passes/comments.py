from pathlib import Path
import re

from cvise.passes.hint_based import HintBasedPass
from cvise.utils.hint import HintBundle


class CommentsPass(HintBasedPass):
    def check_prerequisites(self):
        return True

    def generate_hints(self, test_case: Path):
        prog = test_case.read_bytes()
        hints = []

        # Remove all multiline comments - the pattern is:
        # * first - "/*",
        # * then - any number of "*" that aren't followed by "/", or of any other characters;
        # * finally - "*/".
        for m in re.finditer(rb'/\*(?:\*(?!/)|[^*])*\*/', prog, flags=re.DOTALL):
            hints.append({'t': 0, 'p': [{'l': m.start(), 'r': m.end()}]})

        # Remove all single-line comments.
        for m in re.finditer(rb'//.*$', prog, flags=re.MULTILINE):
            hints.append({'t': 1, 'p': [{'l': m.start(), 'r': m.end()}]})

        # The order must match the 't' indices above.
        vocab = ['multi-line', 'single-line']
        return HintBundle(hints=hints, vocabulary=vocab)

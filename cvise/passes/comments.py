import re

from cvise.passes.hint_based import HintBasedPass
from cvise.utils.hint import HintBundle


class CommentsPass(HintBasedPass):
    def check_prerequisites(self):
        return True

    def generate_hints(self, test_case):
        with open(test_case) as in_file:
            prog = in_file.read()

        hints = []

        # Remove all multiline comments - the pattern is:
        # * first - "/*",
        # * then - any number of "*" that aren't followed by "/", or of any other characters;
        # * finally - "*/".
        for m in re.finditer(r'/\*(?:\*(?!/)|[^*])*\*/', prog, flags=re.DOTALL):
            hints.append({'p': [{'l': m.start(), 'r': m.end(), 't': 0}]})

        # Remove all single-line comments.
        for m in re.finditer(r'//.*$', prog, flags=re.MULTILINE):
            hints.append({'p': [{'l': m.start(), 'r': m.end(), 't': 1}]})

        # The order must match the 't' indices above.
        vocab = ['multi-line', 'single-line']
        return HintBundle(hints=hints, vocabulary=vocab)

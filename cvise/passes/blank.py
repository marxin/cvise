import re

from cvise.passes.hint_based import HintBasedPass
from cvise.utils.hint import HintBundle


class BlankPass(HintBasedPass):
    PATTERNS = {
        'blankline': rb'^\s*$',
        'hashline': rb'^#',
    }

    def check_prerequisites(self):
        return True

    def generate_hints(self, test_case):
        hints = []
        with open(test_case, 'rb') as in_file:
            file_pos = 0
            for line in in_file.readlines():
                end_pos = file_pos + len(line)
                for idx, pattern in enumerate(self.PATTERNS.values()):
                    if re.match(pattern, line) is not None:
                        hints.append({'t': idx, 'p': [{'l': file_pos, 'r': end_pos}]})
                file_pos = end_pos

        # This relies on Python dictionaries keeping the order of keys stable (true since Python 3.7).
        vocab = list(self.PATTERNS.keys())
        return HintBundle(hints=hints, vocabulary=vocab)

from pathlib import Path
import re
from typing import List

from cvise.passes.hint_based import HintBasedPass
from cvise.utils.hint import Hint, HintBundle, Patch


class BlankPass(HintBasedPass):
    PATTERNS = {
        b'blankline': rb'^\s*$',
        b'hashline': rb'^#',
    }

    def check_prerequisites(self):
        return True

    def output_hint_types(self) -> List[bytes]:
        return list(self.PATTERNS.keys())

    def generate_hints(self, test_case: Path, *args, **kwargs):
        hints = []
        with open(test_case, 'rb') as in_file:
            file_pos = 0
            for line in in_file.readlines():
                end_pos = file_pos + len(line)
                for idx, pattern in enumerate(self.PATTERNS.values()):
                    if re.match(pattern, line) is not None:
                        hints.append(Hint(type=idx, patches=[Patch(left=file_pos, right=end_pos)]))
                file_pos = end_pos

        # This relies on Python dictionaries keeping the order of keys stable (true since Python 3.7).
        vocab = list(self.PATTERNS.keys())
        return HintBundle(hints=hints, vocabulary=vocab)

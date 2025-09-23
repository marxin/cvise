from pathlib import Path
import re
from typing import List, Optional

from cvise.passes.hint_based import HintBasedPass
from cvise.utils.hint import Hint, HintBundle, Patch


class BlankPass(HintBasedPass):
    PATTERNS = {
        b'blankline': rb'^\s*$',
        b'hashline': rb'^#',
    }

    def check_prerequisites(self):
        return True

    def supports_dir_test_cases(self):
        return True

    def output_hint_types(self) -> List[bytes]:
        return list(self.PATTERNS.keys())

    def generate_hints(self, test_case: Path, *args, **kwargs):
        # This relies on Python dictionaries keeping the order of keys stable (true since Python 3.7).
        vocab = list(self.PATTERNS.keys())

        hints = []
        if test_case.is_dir():
            for path in test_case.rglob('*'):
                if not path.is_dir() and not path.is_symlink():
                    rel_path = path.relative_to(test_case)
                    vocab.append(str(rel_path).encode())
                    file_id = len(vocab) - 1
                    self._generate_hints_for_file(path, file_id, hints)
        else:
            self._generate_hints_for_file(test_case, file_id=None, hints=hints)

        return HintBundle(hints=hints, vocabulary=vocab)

    def _generate_hints_for_file(self, path: Path, file_id: Optional[int], hints: List[Hint]) -> None:
        with open(path, 'rb') as in_file:
            file_pos = 0
            for line in in_file:
                end_pos = file_pos + len(line)
                for idx, pattern in enumerate(self.PATTERNS.values()):
                    if re.match(pattern, line) is not None:
                        hints.append(Hint(type=idx, patches=[Patch(left=file_pos, right=end_pos, file=file_id)]))
                file_pos = end_pos

from pathlib import Path
import re
from typing import Optional

from cvise.passes.hint_based import HintBasedPass
from cvise.utils.fileutil import filter_files_by_patterns
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

    def output_hint_types(self) -> list[bytes]:
        return list(self.PATTERNS.keys())

    def generate_hints(self, test_case: Path, *args, **kwargs):
        # This relies on Python dictionaries keeping the order of keys stable (true since Python 3.7).
        vocab = list(self.PATTERNS.keys())

        is_dir = test_case.is_dir()
        paths = filter_files_by_patterns(test_case, self.claim_files, self.claimed_by_others_files)
        hints = []
        for path in paths:
            if is_dir:
                rel_path = path.relative_to(test_case)
                vocab.append(str(rel_path).encode())
                file_id = len(vocab) - 1
            else:
                file_id = None
            self._generate_hints_for_file(path, file_id, hints)
        return HintBundle(hints=hints, vocabulary=vocab)

    def _generate_hints_for_file(self, path: Path, file_id: Optional[int], hints: list[Hint]) -> None:
        with open(path, 'rb') as in_file:
            file_pos = 0
            for line in in_file:
                end_pos = file_pos + len(line)
                for idx, pattern in enumerate(self.PATTERNS.values()):
                    if re.match(pattern, line) is not None:
                        hints.append(Hint(type=idx, patches=(Patch(left=file_pos, right=end_pos, file=file_id),)))
                file_pos = end_pos

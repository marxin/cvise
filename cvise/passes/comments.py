from pathlib import Path
import re
from typing import Dict, List, Union

from cvise.passes.hint_based import HintBasedPass
from cvise.utils.hint import Hint, HintBundle, Patch


class CommentsPass(HintBasedPass):
    # The hints vocabulary - strings used by our hint.
    INITIAL_VOCAB = ('multi-line', 'single-line')
    # The indices must match the order in INITIAL_VOCAB.
    MULTI_LINE_VOCAB_ID = 0
    SINGLE_LINE_VOCAB_ID = 1

    def check_prerequisites(self):
        return True

    def supports_dir_test_cases(self):
        return True

    def output_hint_types(self) -> List[str]:
        return list(self.INITIAL_VOCAB)

    def generate_hints(self, test_case: Path, *args, **kwargs):
        vocab = list(self.INITIAL_VOCAB)
        hints = []
        if test_case.is_dir():
            for path in test_case.rglob('*'):
                if not path.is_dir():
                    vocab.append(str(path.relative_to(test_case)))
                    file_id = len(vocab) - 1
                    hints += self._generate_hints_for_file(path, file_id)
        else:
            hints += self._generate_hints_for_file(test_case, file_id=None)
        return HintBundle(hints=hints, vocabulary=vocab)

    def _generate_hints_for_file(self, file_path: Path, file_id: Union[int, None]) -> List[Dict]:
        prog = file_path.read_bytes()

        hints = []

        # Remove all multiline comments - the pattern is:
        # * first - "/*",
        # * then - any number of "*" that aren't followed by "/", or of any other characters;
        # * finally - "*/".
        for m in re.finditer(rb'/\*(?:\*(?!/)|[^*])*\*/', prog, flags=re.DOTALL):
            patch = Patch(left=m.start(), right=m.end())
            if file_id is not None:
                patch.file = file_id
            hints.append(Hint(type=self.MULTI_LINE_VOCAB_ID, patches=[patch]))

        # Remove all single-line comments.
        for m in re.finditer(rb'//.*$', prog, flags=re.MULTILINE):
            patch = Patch(left=m.start(), right=m.end())
            if file_id is not None:
                patch.file = file_id
            hints.append(Hint(type=self.SINGLE_LINE_VOCAB_ID, patches=[patch]))

        return hints

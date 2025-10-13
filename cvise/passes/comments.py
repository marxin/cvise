from pathlib import Path
import re
from typing import Union

from cvise.passes.hint_based import HintBasedPass
from cvise.utils.fileutil import filter_files_by_patterns
from cvise.utils.hint import Hint, HintBundle, Patch


class CommentsPass(HintBasedPass):
    # The hints vocabulary - strings used by our hints.
    INITIAL_VOCAB = (b'multi-line', b'single-line')
    # The indices must match the order in INITIAL_VOCAB.
    MULTI_LINE_VOCAB_ID = 0
    SINGLE_LINE_VOCAB_ID = 1

    def check_prerequisites(self):
        return True

    def supports_dir_test_cases(self):
        return True

    def output_hint_types(self) -> list[bytes]:
        return list(self.INITIAL_VOCAB)

    def generate_hints(self, test_case: Path, *args, **kwargs):
        vocab: list[bytes] = list(self.INITIAL_VOCAB)
        is_dir = test_case.is_dir()
        paths = filter_files_by_patterns(test_case, self.claim_files, self.claimed_by_others_files)
        hints = []
        for path in paths:
            if is_dir:
                rel_path = path.relative_to(test_case)
                vocab.append(str(rel_path).encode())
                path_id = len(vocab) - 1
            else:
                path_id = None
            self._generate_hints_for_file(path, path_id, hints)
        return HintBundle(hints=hints, vocabulary=vocab)

    def _generate_hints_for_file(self, file_path: Path, path_id: Union[int, None], hints: list[Hint]) -> None:
        prog = file_path.read_bytes()

        # Remove all multiline comments - the pattern is:
        # * first - "/*",
        # * then - any number of "*" that aren't followed by "/", or of any other characters;
        # * finally - "*/".
        for m in re.finditer(rb'/\*(?:\*(?!/)|[^*])*\*/', prog, flags=re.DOTALL):
            patch = Patch(left=m.start(), right=m.end(), path=path_id)
            hints.append(Hint(type=self.MULTI_LINE_VOCAB_ID, patches=(patch,)))

        # Remove all single-line comments.
        for m in re.finditer(rb'//.*$', prog, flags=re.MULTILINE):
            patch = Patch(left=m.start(), right=m.end(), path=path_id)
            hints.append(Hint(type=self.SINGLE_LINE_VOCAB_ID, patches=(patch,)))

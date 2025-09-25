from pathlib import Path
from typing import List, Set

from cvise.passes.hint_based import HintBasedPass
from cvise.utils.hint import Hint, HintBundle, Patch


_FILEREF = b'@fileref'
_RM = b'rm'


class RmUnusedFilesPass(HintBasedPass):
    """A pass that deletes files that are deemed to be unused.

    For example, this pass attempts deleting C/C++ headers that aren't included from anywhere. This pass is only
    applicable to test cases that are directories.

    The information about file usage has to be supplied by other passes, like MakefilePass, ClangIncludeGraphPass, etc.,
    in form of "@fileref" hints. Any file that's not mentioned in any of the hints as being referred-by is attempted to
    be deleted.
    """

    def check_prerequisites(self):
        return True

    def supports_dir_test_cases(self):
        return True

    def input_hint_types(self) -> List[bytes]:
        return [_FILEREF]

    def generate_hints(self, test_case: Path, dependee_hints: List[HintBundle], *args, **kwargs):
        if not test_case.is_dir():
            return HintBundle(hints=[])

        referenced_files: Set[Path] = set()
        for bundle in dependee_hints:
            for hint in bundle.hints:
                assert hint.type is not None
                assert bundle.vocabulary[hint.type] == _FILEREF
                assert hint.extra is not None
                referenced_files.add(test_case / bundle.vocabulary[hint.extra].decode())

        all_files = {p for p in test_case.rglob('*') if not p.is_dir()}
        unmentioned_files = sorted(all_files - referenced_files)

        vocab = [_RM] + [str(p.relative_to(test_case)).encode() for p in unmentioned_files]
        hints = []
        for i, path in enumerate(unmentioned_files):
            file_id = i + 1  # matches the position in vocab
            size = path.stat().st_size
            hints.append(Hint(patches=[Patch(left=0, right=size, file=file_id, operation=0)]))
        return HintBundle(hints=hints, vocabulary=vocab)

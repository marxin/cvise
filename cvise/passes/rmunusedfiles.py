from pathlib import Path

from cvise.passes.hint_based import HintBasedPass
from cvise.utils.hint import Hint, HintBundle, Patch

_FILEREF = b'@fileref'
_RM = b'rm'
_RM_UNUSED_FILE = b'rm-unused-file'
_RM_UNUSED_EMPTY_DIR = b'rm-unused-empty-dir'


class RmUnusedFilesPass(HintBasedPass):
    """A pass that deletes files/directories that are deemed to be unused.

    For example, this pass attempts deleting C/C++ headers that aren't included from anywhere. The pass also tries
    deleting empty directories unless they're mentioned in some command lines. This pass is only applicable to test
    cases that are directories.

    The information about file usage has to be supplied by other passes, like MakefilePass, ClangIncludeGraphPass, etc.,
    in form of "@fileref" hints. Any file that's not mentioned in any of the hints as being referred-to is attempted to
    be deleted; same for empty directories.
    """

    def check_prerequisites(self):
        return True

    def supports_dir_test_cases(self):
        return True

    def input_hint_types(self) -> list[bytes]:
        return [_FILEREF]

    def output_hint_types(self) -> list[bytes]:
        return [_RM_UNUSED_FILE, _RM_UNUSED_EMPTY_DIR]

    def generate_hints(self, test_case: Path, dependee_hints: list[HintBundle], *args, **kwargs):
        if not test_case.is_dir():
            return HintBundle(hints=[])

        referenced_paths: set[Path] = set()
        for bundle in dependee_hints:
            for hint in bundle.hints:
                assert hint.type is not None
                assert bundle.vocabulary[hint.type] == _FILEREF
                assert hint.extra is not None
                referenced_paths.add(test_case / bundle.vocabulary[hint.extra].decode())

        all_paths = set(test_case.rglob('*'))
        unmentioned_paths = sorted(all_paths - referenced_paths)

        vocab: list[bytes] = [_RM, _RM_UNUSED_FILE, _RM_UNUSED_EMPTY_DIR]  # the order must match indices below
        hints = []
        for path in unmentioned_paths:
            is_dir = path.is_dir()
            if is_dir and any(path.iterdir()):
                continue  # only attempt deleting empty directories
            vocab.append(str(path.relative_to(test_case)).encode())
            path_id = len(vocab) - 1
            op = 0  # "rm"
            tp = (
                2  # "rm-unused-empty-dir"
                if is_dir
                else 1  # "rm-unused-file"
            )
            hints.append(Hint(type=tp, patches=(Patch(path=path_id, operation=op),)))
        return HintBundle(hints=hints, vocabulary=vocab)

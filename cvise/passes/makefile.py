from enum import Enum, unique
from pathlib import Path
from typing import List

from cvise.passes.hint_based import HintBasedPass
from cvise.utils import makefileparser
from cvise.utils.hint import Hint, HintBundle, Patch


_FILE_NAMES = ('Makefile', 'makefile', 'GNUmakefile')


@unique
class _Vocab(Enum):
    # Items must be listed in the index order; indices must be contiguous and start from zero.
    REMOVE_COMMAND_ARGUMENT = (0, b'remove-command-argument')


class MakefilePass(HintBasedPass):
    """A pass for removing items from makefiles."""

    def check_prerequisites(self):
        return True

    def supports_dir_test_cases(self):
        return True

    def output_hint_types(self) -> List[bytes]:
        return [v.value[1] for v in _Vocab]

    def generate_hints(self, test_case: Path, *args, **kwargs):
        paths = list(test_case.rglob('*')) if test_case.is_dir() else [test_case]
        interesting_paths = [p for p in paths if _interesting_file(p)]

        vocab: List[bytes] = [v.value[1] for v in _Vocab]  # collect all strings used in hints
        hints: List[Hint] = []
        for path in interesting_paths:
            mk = makefileparser.parse(path)
            rel_path = path.relative_to(test_case)
            vocab.append(str(rel_path).encode())
            file_id = len(vocab) - 1
            _create_hints_for_makefile(mk, file_id, hints)

        return HintBundle(hints=hints, vocabulary=vocab)


def _interesting_file(path: Path) -> bool:
    return path.name in _FILE_NAMES


def _create_hints_for_makefile(mk: makefileparser.Makefile, file_id: int, hints: List[Hint]) -> None:
    for rule in mk.rules:
        for recipe_line in rule.recipe:
            for arg in recipe_line.args:
                hints.append(
                    Hint(
                        type=_Vocab.REMOVE_COMMAND_ARGUMENT.value[0],
                        patches=[Patch(left=arg.loc.begin, right=arg.loc.end, file=file_id)],
                    )
                )

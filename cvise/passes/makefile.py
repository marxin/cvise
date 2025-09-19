from enum import Enum, unique
from pathlib import Path
from typing import Dict, List

from cvise.passes.hint_based import HintBasedPass
from cvise.utils import makefileparser
from cvise.utils.hint import Hint, HintBundle, Patch


_FILE_NAMES = ('Makefile', 'makefile', 'GNUmakefile')


@unique
class _Vocab(Enum):
    # Items must be listed in the index order; indices must be contiguous and start from zero.
    REMOVE_ARGUMENT_FROM_ALL_COMMANDS = (0, b'remove-argument-from-all-commands')


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
            rel_path = path.relative_to(test_case)
            vocab.append(str(rel_path).encode())
            file_id = len(vocab) - 1
            _create_hints_for_makefile(path, file_id, hints)

        return HintBundle(hints=hints, vocabulary=vocab)


def _interesting_file(path: Path) -> bool:
    return path.name in _FILE_NAMES


def _create_hints_for_makefile(path: Path, file_id: int, hints: List[Hint]) -> None:
    mk = makefileparser.parse(path)

    arg_to_locs: Dict[bytes, List[makefileparser.SourceLoc]] = {}
    for rule in mk.rules:
        for recipe_line in rule.recipe:
            for arg in recipe_line.args:
                arg_to_locs.setdefault(arg.value, []).append(arg.loc)
    for locs in arg_to_locs.values():
        hints.append(
            Hint(
                type=_Vocab.REMOVE_ARGUMENT_FROM_ALL_COMMANDS.value[0],
                patches=[Patch(left=loc.begin, right=loc.end, file=file_id) for loc in locs],
            )
        )

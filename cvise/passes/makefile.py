from enum import Enum, unique
from pathlib import Path
import re
from typing import Dict, List

from cvise.passes.hint_based import HintBasedPass
from cvise.utils import makefileparser
from cvise.utils.hint import Hint, HintBundle, Patch


_FILE_NAMES = ('Makefile', 'makefile', 'GNUmakefile')
# TODO: make these configurable
_TWO_TOKEN_OPTIONS = re.compile(rb'-I|-iquote|-isystem|-o|-Xclang')
_REMOVAL_BLOCKLIST = re.compile(
    rb'-fallow-pcm-with-compiler-errors|-ferror-limit=.*|-fmax-errors=.*|-fmodule-map-file-home-is-cwd|-fno-crash-diagnostics|-fno-cxx-modules|-fno-implicit-module-maps|-fno-implicit-modules|-fsyntax-only|-I.*|-no-pedantic|--no-pedantic|-nostdinc++|-nostdlib++|--no-warnings|-o.*|-pedantic|--pedantic|-pedantic-errors|--pedantic-errors|-w|-W.*|-fpermissive|-Xclang=-emit-module|-Xclang=-fno-cxx-modules|-Xclang=-fmodule-map-file-home-is-cwd'
)
_TWO_TOKEN_OPTIONS_REMOVAL_BLOCKLIST = re.compile(
    rb'-I .*|-iquote .*|-isystem .*|-o .*|-Xclang -fallow-pcm-with-compiler-errors'
)


@unique
class _Vocab(Enum):
    # Items must be listed in the index order; indices must be contiguous and start from zero.
    REMOVE_ARGUMENTS_ACROSS_ALL_COMMANDS = (0, b'remove-arguments-across-all-commands')


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

    # Removing argument(s) across all commands.
    arg_locs: Dict[bytes, List[makefileparser.SourceLoc]] = {}
    for rule in mk.rules:
        for recipe_line in rule.recipe:
            for arg_group in _get_removable_arg_groups(recipe_line.args):
                key = b' '.join(a.value for a in arg_group)
                arg_locs.setdefault(key, []).extend(a.loc for a in arg_group)
    for locs in arg_locs.values():
        hints.append(
            Hint(
                type=_Vocab.REMOVE_ARGUMENTS_ACROSS_ALL_COMMANDS.value[0],
                patches=[Patch(left=loc.begin, right=loc.end, file=file_id) for loc in locs],
            )
        )


def _get_removable_arg_groups(args: List[makefileparser.TextWithLoc]) -> List[List[makefileparser.TextWithLoc]]:
    two_token_option = None
    removable = []
    for arg in args:
        if two_token_option:
            if not _TWO_TOKEN_OPTIONS_REMOVAL_BLOCKLIST.match(two_token_option.value + b' ' + arg):
                removable.append([two_token_option, arg])
            two_token_option = None
            continue
        if _TWO_TOKEN_OPTIONS.match(arg.value):
            two_token_option = arg
            continue
        if _REMOVAL_BLOCKLIST.match(arg.value):
            continue
        removable.append([arg])
    return removable

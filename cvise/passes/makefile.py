from collections.abc import Sequence
from enum import Enum, unique
from pathlib import Path
import re

from cvise.passes.hint_based import HintBasedPass
from cvise.utils import makefileparser
from cvise.utils.fileutil import filter_files_by_patterns
from cvise.utils.hint import Hint, HintBundle, Patch
from cvise.utils.makefileparser import Makefile, SourceLoc, TextWithLoc


# TODO: make these configurable
_ARG_REMOVAL_PROG_ALLOWLIST = re.compile(r'\bCC\b|clang|CLANG|\bCXX\b|g\+\+|G\+\+|gcc|GCC')
_TWO_TOKEN_OPTIONS = re.compile(rb'-I|-iquote|-isystem|-o|-Xclang')
_REMOVAL_BLOCKLIST = re.compile(
    rb'-fallow-pcm-with-compiler-errors|-ferror-limit=.*|-fmax-errors=.*|-fmodule-map-file-home-is-cwd|'
    + rb'-fno-crash-diagnostics|-fno-cxx-modules|-fno-implicit-module-maps|-fno-implicit-modules|-fpermissive|'
    + rb'-fsyntax-only|-I.*|-no-pedantic|--no-pedantic|-nostdinc\+\+|-nostdlib\+\+|--no-warnings|-o.*|-pedantic|'
    + rb'--pedantic|-pedantic-errors|--pedantic-errors|-w|-W.*|-Xclang=-emit-module|-Xclang=-fno-cxx-modules|'
    + rb'-Xclang=-fmodule-map-file-home-is-cwd'
)
_TWO_TOKEN_OPTIONS_REMOVAL_BLOCKLIST = re.compile(
    rb'-I .*|-iquote .*|-isystem .*|-o .*|-Xclang -fallow-pcm-with-compiler-errors'
)
_FILE_PATH_OPTIONS = re.compile(rb'=(?=(.*))')


@unique
class _Vocab(Enum):
    # Items must be listed in the index order; indices must be contiguous and start from zero.
    MAKEFILE = (0, b'@makefile')  # used to convey makefile file paths to other passes
    FILEREF = (1, b'@fileref')
    REMOVE_ARGUMENTS_ACROSS_ALL_COMMANDS = (2, b'remove-arguments-across-all-commands')
    REMOVE_TARGET = (3, b'remove-target')


class MakefilePass(HintBasedPass):
    """A pass for removing items from makefiles.

    Note: C-Vise JSON config should specify "claim_files" for this pass, to prevent it from being attempted on unrelated
    files and to prevent the makefiles from being corrupted by other passes.
    """

    def __init__(self, claim_files: list[str], **kwargs):
        super().__init__(claim_files=claim_files, **kwargs)

    def check_prerequisites(self):
        return True

    def supports_dir_test_cases(self):
        return True

    def output_hint_types(self) -> list[bytes]:
        return [v.value[1] for v in _Vocab]

    def generate_hints(self, test_case: Path, *args, **kwargs):
        makefiles = filter_files_by_patterns(test_case, self.claim_files, self.claimed_by_others_files)
        vocab: list[bytes] = [v.value[1] for v in _Vocab]  # initial set of strings used in hints
        path_to_vocab: dict[Path, int] = {}
        hints: list[Hint] = []
        for path in makefiles:
            file_id = _get_vocab_id(path.relative_to(test_case), vocab, path_to_vocab)
            _add_file_level_hints(file_id, hints)
            mk = makefileparser.parse(path)
            _add_fileref_hints(mk, file_id, test_case, vocab, path_to_vocab, hints)
            _add_arg_removal_hints(mk, file_id, hints)
            _add_target_removal_hints(mk, file_id, hints)

        return HintBundle(hints=hints, vocabulary=vocab)


def _add_file_level_hints(file_id: int, hints: list[Hint]) -> None:
    hints.append(
        Hint(
            type=_Vocab.MAKEFILE.value[0],
            patches=(),
            extra=file_id,
        )
    )

    # Assume all makefiles to be used (typically the interestingness test would do so), not trying to delete them in
    # RmUnusedFilesPass.
    hints.append(
        Hint(
            type=_Vocab.FILEREF.value[0],
            patches=(),
            extra=file_id,
        )
    )


def _add_fileref_hints(
    mk: Makefile, file_id: int, test_case: Path, vocab: list[bytes], path_to_vocab: dict[Path, int], hints: list[Hint]
) -> None:
    # Heuristically detect mentions of files in command lines in all recipes.
    for rule in mk.rules:
        for recipe_line in rule.recipe:
            prog_path = test_case / Path(recipe_line.program.value.decode())
            if prog_path.is_relative_to(test_case) and prog_path.exists():
                hints.append(
                    Hint(
                        type=_Vocab.FILEREF.value[0],
                        patches=_locs_to_patches([recipe_line.program.loc], file_id),
                        extra=_get_vocab_id(prog_path.relative_to(test_case), vocab, path_to_vocab),
                    )
                )

            for arg in recipe_line.args:
                possible_paths = [arg.value] + [m.group(1) for m in _FILE_PATH_OPTIONS.finditer(arg.value)]
                for path_bytes in possible_paths:
                    arg_path = test_case / Path(path_bytes.decode())
                    if arg_path.is_relative_to(test_case) and arg_path.exists():
                        hints.append(
                            Hint(
                                type=_Vocab.FILEREF.value[0],
                                patches=_locs_to_patches([arg.loc], file_id),
                                extra=_get_vocab_id(arg_path.relative_to(test_case), vocab, path_to_vocab),
                            )
                        )
                        break


def _add_arg_removal_hints(mk: Makefile, file_id: int, hints: list[Hint]) -> None:
    arg_locs: dict[bytes, list[SourceLoc]] = {}

    for rule in mk.rules:
        for recipe_line in rule.recipe:
            if not _ARG_REMOVAL_PROG_ALLOWLIST.search(recipe_line.program.value.decode()):
                continue
            for arg_group in _get_removable_arg_groups(recipe_line.args):
                key = b' '.join(a.value for a in arg_group)
                locs = arg_locs.setdefault(key, [])
                for arg in arg_group:
                    if arg.preceding_spaces_loc:
                        locs.append(arg.preceding_spaces_loc)
                    locs.append(arg.loc)

    for locs in arg_locs.values():
        hints.append(
            Hint(
                type=_Vocab.REMOVE_ARGUMENTS_ACROSS_ALL_COMMANDS.value[0],
                patches=_locs_to_patches(locs, file_id),
            )
        )


def _add_target_removal_hints(mk: Makefile, file_id: int, hints: list[Hint]) -> None:
    # First, collect target names and their locations in recipe headers.
    target_mentions: dict[Path, list[SourceLoc]] = {}
    for rule in mk.rules:
        # Either delete a mention of a target from the rule, or the whole rule if it's the only target in it.
        if len({t.value for t in rule.targets}) == 1:
            target_mentions.setdefault(rule.targets[0].value, []).append(rule.loc)
        else:
            for target in rule.targets:
                mentions = target_mentions.setdefault(target.value, [])
                if target.preceding_spaces_loc:
                    mentions.append(target.preceding_spaces_loc)
                mentions.append(target.loc)

        for prereq in rule.prereqs:
            mentions = target_mentions.setdefault(prereq.value, [])
            if prereq.preceding_spaces_loc:
                mentions.append(prereq.preceding_spaces_loc)
            mentions.append(prereq.loc)

    for to_delete in mk.builtin_targets | mk.phony_targets:
        target_mentions.pop(to_delete, None)

    # Second, heuristically detect mentions of targets in command lines in all recipes.
    for rule in mk.rules:
        for recipe_line in rule.recipe:
            prog = Path(recipe_line.program.value.decode())
            if prog in target_mentions:
                # The whole command has to be deleted if the program name is a known target itself.
                target_mentions[prog].append(recipe_line.loc)
                continue

            for i, arg in enumerate(recipe_line.args):
                prev_arg = recipe_line.args[i - 1] if i > 0 else None
                possible_paths = [arg.value] + [m.group(1) for m in _FILE_PATH_OPTIONS.finditer(arg.value)]

                for path_bytes in possible_paths:
                    path = Path(path_bytes.decode())
                    if path not in target_mentions:
                        continue
                    mentions = target_mentions[path]
                    if arg.preceding_spaces_loc:
                        mentions.append(arg.preceding_spaces_loc)
                    mentions.append(arg.loc)

                    if prev_arg and _TWO_TOKEN_OPTIONS.fullmatch(prev_arg.value):
                        mentions.append(prev_arg.loc)
                        if prev_arg.preceding_spaces_loc:
                            mentions.append(prev_arg.preceding_spaces_loc)
                    break

    # Then generate a hint for each target and all references to it.
    for locs in target_mentions.values():
        hints.append(
            Hint(
                type=_Vocab.REMOVE_TARGET.value[0],
                patches=_locs_to_patches(locs, file_id),
            )
        )


def _get_removable_arg_groups(args: list[TextWithLoc]) -> list[list[TextWithLoc]]:
    two_token_option = None
    removable = []
    for arg in args:
        if two_token_option:
            if not _TWO_TOKEN_OPTIONS_REMOVAL_BLOCKLIST.fullmatch(two_token_option.value + b' ' + arg.value):
                removable.append([two_token_option, arg])
            two_token_option = None
            continue
        if _TWO_TOKEN_OPTIONS.fullmatch(arg.value):
            two_token_option = arg
            continue
        if _REMOVAL_BLOCKLIST.fullmatch(arg.value):
            continue
        removable.append([arg])
    return removable


def _get_vocab_id(path: Path, vocab: list[bytes], path_to_vocab: dict[Path, int]) -> int:
    if path in path_to_vocab:
        return path_to_vocab[path]
    vocab.append(str(path).encode())
    id = len(vocab) - 1
    path_to_vocab[path] = id
    return id


def _locs_to_patches(locs: Sequence[SourceLoc], mk_file_id: int) -> tuple[Patch, ...]:
    return tuple(Patch(left=loc.begin, right=loc.end, file=mk_file_id) for loc in locs)

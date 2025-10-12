from collections.abc import Iterator
from pathlib import Path
import re
from typing import Optional

from cvise.passes.abstract import AbstractPass
from cvise.passes.hint_based import HintBasedPass
from cvise.utils import makefileparser
from cvise.utils.hint import Hint, HintBundle, Patch
from cvise.utils.process import ProcessEventNotifier


# TODO: Make these parameters configurable.
# Only execute clang_include_graph for the makefile recipe commands that start from the following programs. The goal is
# to skip running the tool for non-compiler commands, like "mkdir".
_RECOGNIZED_PROGRAMS = re.compile(r'\bCC\b|clang|CLANG|\bCXX\b|g\+\+|G\+\+|gcc|GCC')
# Remove Clang C/C++ header module references, since built module PCMs aren't available without compiling the whole test
# case. Remove "$(EXTRA_CFLAGS)" since the makefile substitution isn't used here and it'd look like a name of an input
# file.
_REMOVE_ARGS = re.compile(
    r'(-Xclang=)?(-fmodule-map-file=.*|-fmodule-file=.*)|'
    r'\$\(EXTRA_CFLAGS\)'
)
_PRECEDING_ARG_TO_REMOVE = re.compile(r'-Xclang')

# How many jobs to spawn for generating the hints: each job calls the clang_include_graph tool for its portion of
# commands extracted from the makefile. This is used to reduce the wall clock time needed to initialize
# ClangIncludeGraphPass on big inputs.
#
# Implementation-wise, each "job" is an instance of _ClangIncludeGraphMultiplexPass, which generates special hints
# "@clang-include-graph-<number>"; the main pass ClangIncludeGraphPass then just merges them together. This is the
# simplest way to parallelize initialization, reusing the standard C-Vise worker pool and respecting the --n parameter.
_INIT_PARALLELIZATION = 10

_HINT_VOCAB: tuple[bytes] = (b'@fileref',)
_MULTIPLEX_PASS_HINT_TEMPLATE = '@clang-include-graph-{}'


class ClangIncludeGraphPass(HintBasedPass):
    """Extracts information on which C/C++ headers are included and from which files.

    This pass analyzes compilation commands and runs the "clang_include_graph" tool for each of the commands
    (with slightly modified input arguments). The compilation commands are obtained by parsing all makefiles that the
    MakefilePass reported (via the "@makefile" hints).
    """

    def __init__(self, external_programs: dict[str, Optional[str]], **kwargs):
        super().__init__(external_programs=external_programs, **kwargs)

    def check_prerequisites(self):
        return self.check_external_program('clang_include_graph')

    def supports_dir_test_cases(self):
        return True

    def create_subordinate_passes(self) -> list[AbstractPass]:
        assert self.external_programs is not None
        return [_ClangIncludeGraphMultiplexPass(i, self.external_programs) for i in range(_INIT_PARALLELIZATION)]

    def input_hint_types(self) -> list[bytes]:
        return [_MULTIPLEX_PASS_HINT_TEMPLATE.format(i).encode() for i in range(_INIT_PARALLELIZATION)]

    def output_hint_types(self) -> list[bytes]:
        return list(_HINT_VOCAB)

    def generate_hints(self, test_case: Path, dependee_hints: list[HintBundle], *args, **kwargs):
        # Simply merge received hints - the actual work has been done by _ClangIncludeGraphMultiplexPass instances.
        merged_vocab = []
        for bundle in dependee_hints:
            merged_vocab.extend(bundle.vocabulary)
        vocab: list[bytes] = list(_HINT_VOCAB) + sorted(set(merged_vocab))
        text_to_vocab: dict[bytes, int] = {s: i for i, s in enumerate(vocab)}
        hints = [_remap_file_ids(h, b, text_to_vocab) for b in dependee_hints for h in b.hints]
        return HintBundle(hints=list(set(hints)), vocabulary=vocab)


def _remap_file_ids(hint: Hint, bundle: HintBundle, text_to_vocab: dict[bytes, int]) -> Hint:
    assert hint.extra is not None
    patches = tuple(
        Patch(left=p.left, right=p.right, file=None if p.file is None else text_to_vocab[bundle.vocabulary[p.file]])
        for p in hint.patches
    )
    return Hint(type=0, patches=patches, extra=text_to_vocab[bundle.vocabulary[hint.extra]])


class _ClangIncludeGraphMultiplexPass(HintBasedPass):
    """Performs one chunk of the work of ClangIncludeGraphPass, in a separate pass to allow init parallelization.

    Processes commands with indices equal to the specified parameter modulo _INIT_PARALLELIZATION.
    """

    def __init__(self, modulo: int, external_programs: dict[str, Optional[str]]):
        super().__init__(external_programs=external_programs)
        self._modulo = modulo
        self._hint_type = _MULTIPLEX_PASS_HINT_TEMPLATE.format(self._modulo).encode()

    def check_prerequisites(self):
        return self.check_external_program('clang_include_graph')

    def user_visible_name(self) -> str:
        # Attribute this subordinate pass' resource usage to the original pass.
        return 'ClangIncludeGraphPass'

    def supports_dir_test_cases(self):
        return True

    def input_hint_types(self) -> list[bytes]:
        # We obtain the list of parsable makefiles from the MakefilePass heuristic.
        return [b'@makefile']

    def output_hint_types(self) -> list[bytes]:
        return [self._hint_type]

    def generate_hints(
        self,
        test_case: Path,
        process_event_notifier: ProcessEventNotifier,
        dependee_hints: list[HintBundle],
        *args,
        **kwargs,
    ):
        makefiles = _get_makefiles_from_hints(test_case, dependee_hints)
        all_commands = _get_all_makefile_commands(makefiles)
        commands = _get_kth_modulo_n(all_commands, self._modulo, _INIT_PARALLELIZATION)
        tool_path = self.external_programs['clang_include_graph']
        assert tool_path

        vocab: list[bytes] = [self._hint_type]
        path_to_vocab: dict[Path, int] = {}
        hints: set[Hint] = set()
        for cmd in commands:
            proc: list[str] = [tool_path] + cmd
            stdout = process_event_notifier.check_output(proc, cwd=test_case)
            toks = _split_by_null_char(stdout)
            while True:
                try:
                    from_path = Path(next(toks))
                    loc_begin = int(next(toks))
                    loc_end = int(next(toks))
                    to_path = Path(next(toks))
                except StopIteration:
                    break
                to_node = _get_vocab_id(to_path, test_case, vocab, path_to_vocab)
                if to_node is None:
                    continue
                from_node = _get_vocab_id(from_path, test_case, vocab, path_to_vocab)
                # If a file was included from a file inside test case, create a patch pointing to the include directive;
                # otherwise leave the hint patchless (e.g., a system/resource dir header including a standard library
                # header that's included into the test case).
                patches = () if from_node is None else (Patch(left=loc_begin, right=loc_end, file=from_node),)
                hints.add(Hint(type=0, patches=patches, extra=to_node))

        return HintBundle(hints=list(hints), vocabulary=vocab)


def _get_makefiles_from_hints(test_case: Path, dependee_hints: list[HintBundle]) -> list[Path]:
    paths = set()
    for bundle in dependee_hints:
        for hint in bundle.hints:
            assert hint.type is not None
            assert bundle.vocabulary[hint.type] == b'@makefile'
            assert hint.extra is not None
            paths.add(test_case / bundle.vocabulary[hint.extra].decode())
    return list(paths)


def _get_all_makefile_commands(makefiles: list[Path]) -> list[list[str]]:
    commands: list[list[str]] = []
    for mk_path in sorted(makefiles):
        mk = makefileparser.parse(mk_path)
        for rule in mk.rules:
            for recipe_line in rule.recipe:
                prog = recipe_line.program.value.decode()
                if _RECOGNIZED_PROGRAMS.search(prog):
                    commands.append([prog] + _filter_args(recipe_line.args))
    return commands


def _get_kth_modulo_n(commands: list[list[str]], k: int, n: int) -> list[list[str]]:
    return [c for i, c in enumerate(commands) if i % n == k]


def _filter_args(args: list[makefileparser.TextWithLoc]) -> list[str]:
    filtered = []
    for arg in args:
        cur = arg.value.decode()
        if not _REMOVE_ARGS.fullmatch(cur):
            filtered.append(cur)
        elif filtered and _PRECEDING_ARG_TO_REMOVE.fullmatch(filtered[-1]):
            filtered.pop()
    return filtered


def _split_by_null_char(data: bytes) -> Iterator[str]:
    start = 0
    while start < len(data):
        sep = data.find(b'\0', start)
        if sep == -1:  # shouldn't happen normally, but protect from it just in case
            sep = len(data)
        yield data[start:sep].decode()
        start = sep + 1


def _get_vocab_id(path: Path, test_case: Path, vocab: list[bytes], path_to_vocab: dict[Path, int]) -> Optional[int]:
    test_case = test_case.resolve()
    if not path.is_absolute():
        path = test_case / path
    path = path.resolve()
    if not path.is_relative_to(test_case):
        return None
    rel_path = path.relative_to(test_case)
    if rel_path in path_to_vocab:
        return path_to_vocab[rel_path]
    vocab.append(str(rel_path).encode())
    id = len(vocab) - 1
    path_to_vocab[rel_path] = id
    return id

from dataclasses import dataclass
from pathlib import Path
import re
from typing import Dict, Iterator, List, Optional, Set

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


_HINT_VOCAB = (b'@fileref',)


@dataclass(frozen=True, order=True)
class _Edge:
    """Edge in the inclusion graph.

    A node is None if the path is outside the test case (e.g., a test case header includes a system/resourcedir header,
    or vice versa).
    """

    from_path: Path
    from_node: Optional[int]
    loc_begin: int
    loc_end: int
    to_path: Path
    to_node: Optional[int]


class ClangIncludeGraphPass(HintBasedPass):
    """Extracts information on which C/C++ headers are included and from which files."""

    def check_prerequisites(self):
        return self.check_external_program('clang_include_graph')

    def supports_dir_test_cases(self):
        return True

    def output_hint_types(self) -> List[bytes]:
        return list(_HINT_VOCAB)

    def generate_hints(self, test_case: Path, process_event_notifier: ProcessEventNotifier, *args, **kwargs):
        paths = list(test_case.rglob('*')) if test_case.is_dir() else [test_case]
        makefiles = [p for p in paths if p.name in makefileparser.FILE_NAMES]

        commands: List[List[str]] = []
        for mk_path in makefiles:
            mk = makefileparser.parse(mk_path)
            for rule in mk.rules:
                for recipe_line in rule.recipe:
                    prog = recipe_line.program.value.decode()
                    if not _RECOGNIZED_PROGRAMS.search(prog):
                        continue
                    cmd = [prog] + _filter_args(recipe_line.args)
                    commands.append(cmd)

        vocab: List[bytes] = list(_HINT_VOCAB)
        path_to_vocab: Dict[Path, int] = {}
        edges: Set[_Edge] = set()
        for cmd in commands:
            proc = [self.external_programs['clang_include_graph']] + cmd
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
                from_node = _get_vocab_id(from_path, test_case, vocab, path_to_vocab)
                to_node = _get_vocab_id(to_path, test_case, vocab, path_to_vocab)
                edges.add(
                    _Edge(
                        from_path=from_path,
                        from_node=from_node,
                        loc_begin=loc_begin,
                        loc_end=loc_end,
                        to_path=to_path,
                        to_node=to_node,
                    )
                )

        hints: List[Hint] = []
        for e in sorted(edges):
            if e.to_node is not None:
                # If a file was included from a file inside test case, create a patch pointing to the include directive;
                # otherwise leave the hint patchless (e.g., a system/resource dir header including a standard library
                # header that's included into the test case).
                patches = () if e.from_node is None else (Patch(left=e.loc_begin, right=e.loc_end, file=e.from_node),)
                hints.append(Hint(type=0, patches=patches, extra=e.to_node))
        return HintBundle(hints=hints, vocabulary=vocab)


def _filter_args(args: List[makefileparser.TextWithLoc]) -> List[str]:
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


def _get_vocab_id(path: Path, test_case: Path, vocab: List[bytes], path_to_vocab: Dict[Path, int]) -> Optional[int]:
    if not path.is_absolute():
        path = (test_case / path).resolve()
    if not path.is_relative_to(test_case):
        return None
    rel_path = path.relative_to(test_case)
    if rel_path in path_to_vocab:
        return path_to_vocab[rel_path]
    vocab.append(str(rel_path).encode())
    id = len(vocab) - 1
    path_to_vocab[rel_path] = id
    return id

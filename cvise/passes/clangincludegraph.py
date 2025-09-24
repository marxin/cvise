from enum import Enum, unique
from pathlib import Path
import re
from typing import Dict, Iterator, List, Optional, Set, Tuple

from cvise.passes.hint_based import HintBasedPass
from cvise.utils import makefileparser
from cvise.utils.hint import Hint, HintBundle, Patch
from cvise.utils.process import ProcessEventNotifier


_RECOGNIZED_PROGRAMS = re.compile(r'\bCC\b|clang|CLANG|\bCXX\b|g++|G++|gcc|GCC')
_SIMPLE_OPTIONS = r'-no-canonical-prefixes|-nostdinc|-nostdinc++|--no-sysroot-suffix'
_PARAMETERIZED_OPTIONS = r'-B|-D|--embed-dir|-I|-idirafter|-imultilib|-iplugindir|-iprefix|-iquote|-isysroot|-isystem|-iwithprefix|-iwithprefixbefore|--sysroot'
_INPUT_FILE_NAMES = re.compile(r'[^-].*\.(c|C|c\+\+|cc|cp|cpp|CPP|cppm|cppmap|cxx|h|H||h\+\+hp|hpp|HPP|hxx|modulemap)')
_ONE_TOK_OPTIONS = re.compile(f'({_SIMPLE_OPTIONS})|(({_PARAMETERIZED_OPTIONS}).+)')
_TWO_TOK_OPTIONS = re.compile(_PARAMETERIZED_OPTIONS)
_HINT_VOCAB = (b'@fileref',)


class ClangIncludeGraphPass(HintBasedPass):
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
                    program = recipe_line.program.value.decode()
                    if _RECOGNIZED_PROGRAMS.match(program):
                        commands.append(_get_args_for_preprocessor(recipe_line.args, mk_path))

        graph: Dict[Tuple[Path, int, int], Set[Path]] = {}
        for command in commands:
            proc = [self.external_programs['clang_include_graph']] + command
            stdout = process_event_notifier.check_output(proc)
            toks = _split_by_null_char(stdout)
            while True:
                try:
                    from_path = Path(next(toks))
                    left_loc = int(next(toks))
                    right_loc = int(next(toks))
                    to_path = Path(next(toks))
                except StopIteration:
                    break
                graph.setdefault((from_path, left_loc, right_loc), set()).add(to_path)

        vocab: List[bytes] = list(_HINT_VOCAB)
        path_to_vocab: Dict[Path, int] = {}
        hints: List[Hint] = []
        for (from_path, left_loc, right_loc), to_path_set in graph.items():
            for to_path in to_path_set:
                from_id = _get_vocab_id(from_path, test_case, vocab, path_to_vocab)
                to_id = _get_vocab_id(to_path, test_case, vocab, path_to_vocab)
                # TODO: support edges from an external header back into the header in the test case
                if from_id is not None and to_id is not None:
                    hints.append(
                        Hint(type=0, patches=[Patch(left=left_loc, right=right_loc, file=from_id)], extra=to_id)
                    )
        return HintBundle(hints=hints, vocabulary=vocab)


def _get_args_for_preprocessor(args: List[makefileparser.TextWithLoc], mk_path: Path) -> List[str]:
    input_files = []
    options = []
    i = 0
    while i < len(args):
        cur = args[i].value.decode()
        next = args[i + 1].value.decode() if i + 1 < len(args) else None
        if _ONE_TOK_OPTIONS.fullmatch(cur):
            options.append(cur)
            i += 1
        elif next is not None and _TWO_TOK_OPTIONS.fullmatch(cur):
            options += [cur, next]
            i += 2
        elif _INPUT_FILE_NAMES.fullmatch(cur):
            input_files.append(Path(cur))
            i += 1
        else:
            i += 1
    return [str(mk_path.parent / p) for p in input_files] + ['--'] + options


def _split_by_null_char(data: bytes) -> Iterator[str]:
    start = 0
    while start < len(data):
        sep = data.find(b'\0', start)
        if sep == -1:
            sep = len(data)
        yield data[start:sep].decode()
        start = sep + 1


def _get_vocab_id(path: Path, test_case: Path, vocab: List[bytes], path_to_vocab: Dict[Path, int]) -> Optional[int]:
    if not path.is_relative_to(test_case):
        return None
    rel_path = path.relative_to(test_case)
    if rel_path in path_to_vocab:
        return path_to_vocab[rel_path]
    vocab.append(str(rel_path).encode())
    id = len(vocab) - 1
    path_to_vocab[rel_path] = id
    return id

from __future__ import annotations
import copy
from dataclasses import dataclass
from enum import Enum, unique
import fnmatch
from pathlib import Path
import re
from typing import Dict, List, Union

from cvise.passes.hint_based import HintBasedPass
from cvise.utils.hint import Hint, HintBundle, Patch


_FILE_PATTERNS = ('*.cppmap', '*.modulemap')


@unique
class _Vocab(Enum):
    # Items must be listed in the index order; indices must be contiguous and start from zero.
    FILEREF = (0, b'@fileref')
    MAKE_HEADER_NON_MODULAR = (1, b'make-header-non-modular')
    DELETE_USE_DECL = (2, b'delete-use-decl')
    DELETE_EMPTY_SUBMODULE = (3, b'delete-empty-submodule')
    INLINE_SUBMODULE_CONTENTS = (4, b'inline-submodule-contents')
    DELETE_LINE = (5, b'delete-line')


class ClangModuleMapPass(HintBasedPass):
    """A pass for removing items from C++ header module map files.

    See https://clang.llvm.org/docs/Modules.html#module-map-language for the specification.
    """

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
        path_to_vocab: Dict[Path, int] = {}
        hints: List[Hint] = []
        for path in interesting_paths:
            file = _parse_file(path)

            rel_path = path.relative_to(test_case)
            file_id = _get_vocab_id(rel_path, vocab, path_to_vocab)

            for mod in file.modules:
                _create_hints_for_module(
                    mod, test_case, file_id, toplevel=True, hints=hints, vocab=vocab, path_to_vocab=path_to_vocab
                )
            _create_hints_for_unclassified_lines(file.unclassified_lines, file_id, hints)

        return HintBundle(hints=hints, vocabulary=vocab)


def _interesting_file(path: Path) -> bool:
    if path.is_dir() or path.is_symlink():
        return False
    return any(fnmatch.fnmatch(path.name, p) for p in _FILE_PATTERNS)


@dataclass
class _SourceLoc:
    begin: int
    end: int


@dataclass
class _HeaderDecl:
    loc: _SourceLoc
    file_path: str


@dataclass
class _UseDecl:
    loc: _SourceLoc
    id: str


@dataclass
class _ModuleDecl:
    loc: _SourceLoc
    title_loc: _SourceLoc  # location of " ... module ... {"
    close_brace_loc: _SourceLoc
    id: str
    headers: List[_HeaderDecl]
    uses: List[_UseDecl]
    submodules: List[_ModuleDecl]


@dataclass
class _ModuleMapFile:
    modules: List[_ModuleDecl]
    unclassified_lines: List[_SourceLoc]


def _get_vocab_id(path: Path, vocab: List[bytes], path_to_vocab: Dict[Path, int]) -> int:
    if path in path_to_vocab:
        return path_to_vocab[path]
    vocab.append(str(path).encode())
    id = len(vocab) - 1
    path_to_vocab[path] = id
    return id


def _create_hints_for_module(
    mod: _ModuleDecl,
    test_case: Path,
    file_id: int,
    toplevel: bool,
    hints: List[Hint],
    vocab: List[bytes],
    path_to_vocab: Dict[Path, int],
) -> None:
    empty = not mod.headers and not mod.uses and not mod.submodules
    if not toplevel and empty:
        hints.append(
            Hint(
                type=_Vocab.DELETE_EMPTY_SUBMODULE.value[0],
                patches=(
                    Patch(
                        file=file_id,
                        left=mod.loc.begin,
                        right=mod.loc.end,
                    ),
                ),
            )
        )

    if not toplevel and not empty:
        hints.append(
            Hint(
                type=_Vocab.INLINE_SUBMODULE_CONTENTS.value[0],
                patches=(
                    Patch(
                        file=file_id,
                        left=mod.title_loc.begin,
                        right=mod.title_loc.end,
                    ),
                    Patch(
                        file=file_id,
                        left=mod.close_brace_loc.begin,
                        right=mod.close_brace_loc.end,
                    ),
                ),
            )
        )

    for header in mod.headers:
        if (test_case / header.file_path).exists():
            header_file_id = _get_vocab_id(Path(header.file_path), vocab, path_to_vocab)
            hints.append(
                Hint(
                    type=_Vocab.FILEREF.value[0],
                    patches=(
                        Patch(
                            file=file_id,
                            left=header.loc.begin,
                            right=header.loc.end,
                        ),
                    ),
                    extra=header_file_id,
                )
            )
        hints.append(
            Hint(
                type=_Vocab.MAKE_HEADER_NON_MODULAR.value[0],
                patches=(
                    Patch(
                        file=file_id,
                        left=header.loc.begin,
                        right=header.loc.end,
                    ),
                ),
            )
        )
    for use in mod.uses:
        hints.append(
            Hint(
                type=_Vocab.DELETE_USE_DECL.value[0],
                patches=(
                    Patch(
                        file=file_id,
                        left=use.loc.begin,
                        right=use.loc.end,
                    ),
                ),
            )
        )
    for submod in mod.submodules:
        _create_hints_for_module(
            submod, test_case, file_id, toplevel=False, hints=hints, vocab=vocab, path_to_vocab=path_to_vocab
        )


def _create_hints_for_unclassified_lines(unclassified_lines: List[_SourceLoc], file_id: int, hints: List[Hint]) -> None:
    for loc in unclassified_lines:
        hints.append(
            Hint(
                type=_Vocab.DELETE_LINE.value[0],
                patches=(
                    Patch(
                        file=file_id,
                        left=loc.begin,
                        right=loc.end,
                    ),
                ),
            )
        )


def _parse_file(path: Path) -> _ModuleMapFile:
    file = _ModuleMapFile(modules=[], unclassified_lines=[])
    with open(path, 'rb') as f:
        stack: List[_ModuleDecl] = []
        file_pos = 0
        for line in f:
            loc = _SourceLoc(begin=file_pos, end=file_pos + len(line))
            file_pos = loc.end

            for ancestor in stack:
                ancestor.loc.end = loc.end  # expand each active module to cover the current line

            if module := _try_parse_module_decl(line, loc):
                parent_children = stack[-1].submodules if stack else file.modules
                parent_children.append(module)
                stack.append(module)
            elif stack and (header := _try_parse_header_decl(line, loc)):
                stack[-1].headers.append(header)
            elif stack and (use := _try_parse_use_decl(line, loc)):
                stack[-1].uses.append(use)
            elif stack and _is_close_brace(line):
                stack[-1].close_brace_loc = loc
                stack.pop()
            else:
                file.unclassified_lines.append(loc)

    return file


def _try_parse_module_decl(line: bytes, loc: _SourceLoc) -> Union[_ModuleDecl, None]:
    m = re.match(rb'.*\bmodule\s+(\S+).*{\s*', line)
    if not m:
        return None
    module_id = m.group(1).decode().strip('"')
    title_loc = copy.copy(loc)
    # close_brace_loc will be replaced with a real value once the closing brace line is parsed
    close_brace_loc = title_loc
    return _ModuleDecl(
        loc=loc,
        title_loc=title_loc,
        close_brace_loc=close_brace_loc,
        id=module_id,
        headers=[],
        uses=[],
        submodules=[],
    )


def _try_parse_header_decl(line: bytes, loc: _SourceLoc) -> Union[_HeaderDecl, None]:
    m = re.match(rb'.*\bheader\s+"([^\s"]+)".*', line)
    if not m:
        return None
    file_path = m.group(1).decode()
    return _HeaderDecl(loc=loc, file_path=file_path)


def _try_parse_use_decl(line: bytes, loc: _SourceLoc) -> Union[_UseDecl, None]:
    m = re.match(rb'.*\buse\s+(\S+).*', line)
    if not m:
        return None
    module_id = m.group(1).decode().strip('"')
    return _UseDecl(loc=loc, id=module_id)


def _is_close_brace(line: bytes) -> bool:
    return line.strip() == b'}'

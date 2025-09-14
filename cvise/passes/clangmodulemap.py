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
    MAKE_HEADER_NON_MODULAR = (0, 'make-header-non-modular')
    DELETE_USE_DECL = (1, 'delete-use-decl')
    DELETE_EMPTY_SUBMODULE = (2, 'delete-empty-submodule')
    INLINE_SUBMODULE_CONTENTS = (3, 'inline-submodule-contents')
    DELETE_LINE = (4, 'delete-line')


class ClangModuleMapPass(HintBasedPass):
    """A pass for removing items from C++ header module map files.

    See https://clang.llvm.org/docs/Modules.html#module-map-language for the specification.
    """

    def check_prerequisites(self):
        return True

    def supports_dir_test_cases(self):
        return True

    def output_hint_types(self) -> List[str]:
        return [v.value[1] for v in _Vocab]

    def generate_hints(self, test_case: Path, *args, **kwargs):
        paths = list(test_case.rglob('*')) if test_case.is_dir() else [test_case]
        interesting_paths = [p for p in paths if _interesting_file(p)]

        vocab: List[str] = [v.value[1] for v in _Vocab]  # collect all strings used in hints
        hints: List[Dict] = []
        for path in interesting_paths:
            file = _parse_file(path)

            vocab.append(str(path.relative_to(test_case)))
            file_id = len(vocab) - 1

            for mod in file.modules:
                _create_hints_for_module(mod, file_id, toplevel=True, hints=hints)
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


def _create_hints_for_module(mod: _ModuleDecl, file_id: int, toplevel: bool, hints: List[Dict]) -> None:
    empty = not mod.headers and not mod.uses and not mod.submodules
    if not toplevel and empty:
        hints.append(
            Hint(
                t=_Vocab.DELETE_EMPTY_SUBMODULE.value[0],
                p=[
                    Patch(
                        f=file_id,
                        l=mod.loc.begin,
                        r=mod.loc.end,
                    )
                ],
            )
        )

    if not toplevel and not empty:
        hints.append(
            Hint(
                t=_Vocab.INLINE_SUBMODULE_CONTENTS.value[0],
                p=[
                    Patch(
                        f=file_id,
                        l=mod.title_loc.begin,
                        r=mod.title_loc.end,
                    ),
                    Patch(
                        f=file_id,
                        l=mod.close_brace_loc.begin,
                        r=mod.close_brace_loc.end,
                    ),
                ],
            )
        )

    for header in mod.headers:
        hints.append(
            Hint(
                t=_Vocab.MAKE_HEADER_NON_MODULAR.value[0],
                p=[
                    Patch(
                        f=file_id,
                        l=header.loc.begin,
                        r=header.loc.end,
                    )
                ],
            )
        )
    for use in mod.uses:
        hints.append(
            Hint(
                t=_Vocab.DELETE_USE_DECL.value[0],
                p=[
                    Patch(
                        f=file_id,
                        l=use.loc.begin,
                        r=use.loc.end,
                    )
                ],
            )
        )
    for submod in mod.submodules:
        _create_hints_for_module(submod, file_id, toplevel=False, hints=hints)


def _create_hints_for_unclassified_lines(unclassified_lines: List[_SourceLoc], file_id: int, hints: List[Dict]) -> None:
    for loc in unclassified_lines:
        hints.append(
            Hint(
                t=_Vocab.DELETE_LINE.value[0],
                p=[
                    Patch(
                        f=file_id,
                        l=loc.begin,
                        r=loc.end,
                    )
                ],
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

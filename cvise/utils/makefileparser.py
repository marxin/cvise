from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
import shlex
from typing import List, Optional, Set


@dataclass
class SourceLoc:
    begin: int
    end: int


@dataclass
class TextWithLoc:
    loc: SourceLoc
    value: bytes

    def substr(self, begin: int, end: Optional[int] = None) -> TextWithLoc:
        assert self.loc.begin + begin <= self.loc.end
        if end is not None:
            assert self.loc.begin + begin <= self.loc.begin + end <= self.loc.end
        return TextWithLoc(
            SourceLoc(self.loc.begin + begin, self.loc.end if end is None else self.loc.begin + end),
            self.value[begin:end],
        )


@dataclass
class PathWithLoc:
    loc: SourceLoc
    value: Path


@dataclass
class RecipeLine:
    loc: SourceLoc
    program: TextWithLoc
    args: List[TextWithLoc]


@dataclass
class Rule:
    loc: SourceLoc
    targets: List[PathWithLoc]
    prereqs: List[PathWithLoc]
    recipe: List[RecipeLine]
    unclassified_lines: List[TextWithLoc]


@dataclass
class Makefile:
    rules: List[Rule]
    unclassified_lines: List[TextWithLoc]
    phony_targets: Set[Path]


def parse(makefile_path: Path) -> Makefile:
    lines: List[bytearray] = []
    with open(makefile_path, 'rb') as f:
        for cur_s in f:
            cur = bytearray(cur_s)
            if lines and lines[-1].rstrip(b'\r\n').endswith(b'\\'):
                pos = lines[-1].rfind(b'\\')
                # TODO: Correctly handle line continuations, without introducing extra spaces.
                lines[-1][pos] = ord(b' ')
                if cur.startswith(b'\t'):
                    cur[0] = ord(b' ')
                lines[-1].extend(cur)
            else:
                lines.append(cur)

    mk = Makefile(rules=[], unclassified_lines=[], phony_targets=set())
    file_pos = 0
    for line in lines:
        loc = SourceLoc(begin=file_pos, end=file_pos + len(line))
        line_with_loc = TextWithLoc(loc, line)
        file_pos = loc.end
        if mk.rules and (recipe := _parse_recipe_line(line_with_loc)):
            rule = mk.rules[-1]
            rule.loc.end = loc.end
            rule.recipe.append(recipe)
        elif rule := _parse_rule_line(line_with_loc):
            mk.rules.append(rule)
        elif mk.rules:
            rule = mk.rules[-1]
            rule.loc.end = loc.end
            rule.unclassified_lines.append(loc)
        else:
            mk.unclassified_lines.append(loc)

    if phony_rule := _find_phony_rule(mk):
        mk.phony_targets = {t.value for t in phony_rule.prereqs}
    return mk


def _parse_rule_line(line: TextWithLoc) -> Optional[Rule]:
    if line.value.startswith(b'\t'):
        return None
    semicolon_pos = line.value.find(b':')
    if semicolon_pos == -1:
        return None
    comment_start = line.value.find(b'#')
    if comment_start != -1:
        if semicolon_pos >= comment_start:
            return None
        line = line.substr(0, comment_start)

    before_semicolon = line.substr(0, semicolon_pos)
    targets = _to_paths(_get_tok_locs(before_semicolon, before_semicolon.value.split()))

    after_semicolon = line.substr(semicolon_pos + 1)
    prereqs = _to_paths(_get_tok_locs(after_semicolon, after_semicolon.value.split()))

    # Loc, recipe, unclassified_lines may get updated later when parsing recipe lines.
    return Rule(loc=line.loc, targets=targets, prereqs=prereqs, recipe=[], unclassified_lines=[])


def _parse_recipe_line(line: TextWithLoc) -> Optional[RecipeLine]:
    if not line.value.startswith(b'\t'):
        return None
    line = line.substr(1)
    if line.value.startswith(b'@'):
        line = line.substr(1)
    cmd_toks = [s.encode() for s in shlex.split(line.value.decode(), comments=True)]
    cmd_tok_locs = _get_tok_locs(line, cmd_toks)
    if not cmd_tok_locs:
        return None
    return RecipeLine(loc=line.loc, program=cmd_tok_locs[0], args=cmd_tok_locs[1:])


def _get_tok_locs(text: TextWithLoc, tokens: List[bytes]) -> List[TextWithLoc]:
    start_pos = 0
    tok_locs = []
    for tok in tokens:
        # Determine the token's position - split() doesn't return how many whitespaces were skipped.
        pos = text.value.find(tok, start_pos)
        assert pos != -1
        begin = text.loc.begin + pos
        end = begin + len(tok)
        tok_loc = SourceLoc(begin=begin, end=end)
        tok_locs.append(TextWithLoc(loc=tok_loc, value=tok))
        start_pos = pos + len(tok)
    return tok_locs


def _to_paths(toks: List[TextWithLoc]) -> List[PathWithLoc]:
    return [PathWithLoc(tok.loc, Path(str(tok.value))) for tok in toks]


def _find_phony_rule(file: Makefile) -> Optional[Rule]:
    for rule in file.rules:
        for target in rule.targets:
            if target.value == '.PHONY':
                return rule
    return None

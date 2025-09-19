from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Set


@dataclass
class SourceLoc:
    begin: int
    end: int


@dataclass
class TextWithLoc:
    loc: SourceLoc
    value: bytes


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
    with open(makefile_path, 'rb') as f:
        lines: List[bytes] = []
        for s in f:
            if lines and lines[-1].rstrip(b'\r\n').endswith(b'\\'):
                pos = lines[-1].rfind(b'\\')
                # TODO: Correctly handle line continuations, without introducing an extra space.
                lines[-1][pos] = ord(b' ')
                if s.startswith(b'\t'):
                    s[0] = ord(b' ')
                lines[-1] += s
            else:
                lines.append(s)

    mk = Makefile(rules=[], unclassified_lines=[], phony_targets=[])
    file_pos = 0
    for line in lines:
        loc = SourceLoc(begin=file_pos, end=file_pos + len(line))
        file_pos = loc.end
        if mk.rules and (recipe := _parse_recipe_line(line, loc)):
            rule = mk.rules[-1]
            rule.loc.end = loc.end
            rule.recipe.append(recipe)
        elif rule := _parse_rule_line(line, loc):
            mk.rules.append(rule)
        elif mk.rules:
            rule = mk.rules[-1]
            rule.loc.end = loc.end
            rule.unclassified_lines.append(loc)
        else:
            mk.unclassified_lines.append(loc)

    if phony_rule := _find_phony_rule(mk):
        mk.phony_targets = [t.value for t in phony_rule.prereqs]
    return mk


def _parse_rule_line(line: bytes, loc: SourceLoc) -> Optional[Rule]:
    if line.startswith(b'\t'):
        return None
    semicolon_pos = line.find(b':')
    if semicolon_pos == -1:
        return None
    comment_start = line.find(b'#')
    if comment_start != -1:
        if semicolon_pos >= comment_start:
            return None
        line = line[:comment_start]
    targets = _to_path_with_locs(_split(line[:semicolon_pos], loc))
    prereqs = _to_path_with_locs(_split(line[semicolon_pos + 1 :], loc))
    # Loc, recipe, unclassified_lines will be updated to real values later.
    return Rule(loc=loc, targets=targets, prereqs=prereqs, recipe=[], unclassified_lines=[])


def _parse_recipe_line(line: bytes, loc: SourceLoc) -> Optional[RecipeLine]:
    if not line.startswith(b'\t'):
        return None
    loc.begin += 1
    line = line[1:]
    if line.startswith(b'@'):
        loc.begin += 1
        line = line[1:]
    cmd = _split(line, loc)
    if not cmd:
        return None
    return RecipeLine(loc=loc, program=cmd[0], args=cmd[1:])


def _split(text: bytes, loc: SourceLoc) -> List[TextWithLoc]:
    start_pos = 0
    toks = []
    for tok in text.split():
        # Determine the token's position - split() doesn't return how many whitespaces were skipped.
        pos = text.find(tok, start_pos)
        assert pos != -1
        begin = loc.begin + pos
        end = begin + len(tok)
        tok_loc = SourceLoc(begin=begin, end=end)
        toks.append(TextWithLoc(loc=tok_loc, value=tok))
        start_pos = pos + len(tok)
    return toks


def _to_path_with_locs(toks: List[TextWithLoc]) -> List[PathWithLoc]:
    return [PathWithLoc(tok.loc, Path(str(tok.value))) for tok in toks]


def _find_phony_rule(file: Makefile) -> Optional[Rule]:
    for rule in file.rules:
        for target in rule.targets:
            if target.value == '.PHONY':
                return rule
    return None

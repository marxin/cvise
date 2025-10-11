from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path


_BUILTIN_TARGETS = (
    Path('.DEFAULT'),
    Path('.DELETE_ON_ERROR'),
    Path('.EXPORT_ALL_VARIABLES'),
    Path('.IGNORE'),
    Path('.INTERMEDIATE'),
    Path('.LOW_RESOLUTION_TIME'),
    Path('.NOTINTERMEDIATE'),
    Path('.NOTPARALLEL'),
    Path('.ONESHELL'),
    Path('.PHONY'),
    Path('.POSIX'),
    Path('.PRECIOUS'),
    Path('.SECONDARY'),
    Path('.SECONDEXPANSION'),
    Path('.SILENT'),
    Path('.SUFFIXES'),
)


@dataclass
class SourceLoc:
    begin: int
    end: int


@dataclass
class TextWithLoc:
    loc: SourceLoc
    value: bytes
    preceding_spaces_loc: SourceLoc | None = None

    def substr(self, begin: int, end: int | None = None) -> TextWithLoc:
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
    preceding_spaces_loc: SourceLoc | None = None


@dataclass
class RecipeLine:
    loc: SourceLoc
    program: TextWithLoc
    args: list[TextWithLoc]


@dataclass
class Rule:
    loc: SourceLoc
    targets: list[PathWithLoc]
    prereqs: list[PathWithLoc]
    recipe: list[RecipeLine]
    unclassified_lines: list[TextWithLoc]


@dataclass
class Makefile:
    rules: list[Rule]
    unclassified_lines: list[TextWithLoc]
    builtin_targets: set[Path]
    phony_targets: set[Path]


def parse(makefile_path: Path) -> Makefile:
    lines: list[bytearray] = []
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

    mk = Makefile(rules=[], unclassified_lines=[], builtin_targets=set(), phony_targets=set())
    file_pos = 0
    for line in lines:
        loc = SourceLoc(begin=file_pos, end=file_pos + len(line))
        line_with_loc = TextWithLoc(loc, bytes(line))
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
            rule.unclassified_lines.append(line_with_loc)
        else:
            mk.unclassified_lines.append(line_with_loc)

    # Collect the names of all special/phony targets.
    for rule in mk.rules:
        mk.builtin_targets.update(t.value for t in rule.targets if t.value in _BUILTIN_TARGETS)
        if any(t.value == Path('.PHONY') for t in rule.targets):
            mk.phony_targets.update(t.value for t in rule.prereqs)

    return mk


def _parse_rule_line(line: TextWithLoc) -> Rule | None:
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
    targets = _to_paths(_split_by_spaces(before_semicolon))

    after_semicolon = line.substr(semicolon_pos + 1)
    prereqs = _to_paths(_split_by_spaces(after_semicolon))

    # Loc, recipe, unclassified_lines may get updated later when parsing recipe lines.
    return Rule(loc=line.loc, targets=targets, prereqs=prereqs, recipe=[], unclassified_lines=[])


def _parse_recipe_line(line: TextWithLoc) -> RecipeLine | None:
    if not line.value.startswith(b'\t'):
        return None
    line = line.substr(1)
    if line.value.startswith(b'@'):
        line = line.substr(1)
    cmd_tok_locs = _split_shell_cmd_line(line)
    if not cmd_tok_locs:
        return None
    return RecipeLine(loc=line.loc, program=cmd_tok_locs[0], args=cmd_tok_locs[1:])


def _split_by_spaces(text: TextWithLoc) -> list[TextWithLoc]:
    start_pos = 0
    tok_locs = []
    for tok in text.value.split():
        # Determine the token's position - split() doesn't return how many whitespaces were skipped.
        pos = text.value.find(tok, start_pos)
        assert pos != -1
        tok_loc = text.substr(pos, pos + len(tok))
        if pos > start_pos:
            tok_loc.preceding_spaces_loc = SourceLoc(text.loc.begin + start_pos, text.loc.begin + pos)
        tok_locs.append(tok_loc)
        start_pos = pos + len(tok)
    return tok_locs


def _split_shell_cmd_line(text: TextWithLoc) -> list[TextWithLoc]:
    # Note: not using shlex because it doesn't report token locations.

    tok_locs = []
    i = 0
    n = len(text.value)
    while i < n:
        # Skip spaces before the next token.
        start = i
        while i < n and chr(text.value[i]).isspace():
            i += 1
        if i == n:
            break
        preceding_spaces_loc = SourceLoc(text.loc.begin + start, text.loc.begin + i) if start < i else None

        begin = i
        tok = bytearray()
        active_quote = None
        while i < n:
            c = chr(text.value[i])
            if c in ('"', "'"):
                if c == active_quote:  # quotes end
                    active_quote = None
                    i += 1
                    continue
                if not active_quote:  # quotes start
                    active_quote = c
                    i += 1
                    continue
            elif (
                c == '\\'
                and active_quote == '"'
                and i + 1 < n
                and text.value[i + 1] in ('$', '`', '"', '\\', '\n', '\r')
            ):  # backslash escape sequence
                tok.append(text.value[i + 1])
                i += 2
                continue
            elif c.isspace() and not active_quote:
                break
            tok.append(ord(c))
            i += 1

        loc = SourceLoc(begin=text.loc.begin + begin, end=text.loc.begin + i)
        tok_locs.append(TextWithLoc(loc, bytes(tok), preceding_spaces_loc))

    return tok_locs


def _to_paths(toks: list[TextWithLoc]) -> list[PathWithLoc]:
    return [PathWithLoc(tok.loc, Path(tok.value.decode()), tok.preceding_spaces_loc) for tok in toks]

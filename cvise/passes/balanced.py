import re
from dataclasses import dataclass
from enum import Enum, auto, unique
from pathlib import Path

from cvise.passes.hint_based import HintBasedPass
from cvise.utils import nestedmatcher
from cvise.utils.error import UnknownArgumentError
from cvise.utils.fileutil import filter_files_by_patterns
from cvise.utils.hint import Hint, HintBundle, Patch


@unique
class Deletion(Enum):
    ALL = auto()
    ONLY = auto()
    INSIDE = auto()


@dataclass
class Config:
    search: nestedmatcher.BalancedExpr
    to_delete: Deletion
    replacement: str = ''
    search_prefix: str = ''


class BalancedPass(HintBasedPass):
    def check_prerequisites(self):
        return True

    def supports_dir_test_cases(self):
        return True

    def generate_hints(self, test_case: Path, *args, **kwargs):
        config = self.__get_config()
        vocabulary = []
        if config.replacement:
            assert config.to_delete == Deletion.ALL
            vocabulary.append(config.replacement.encode())

        is_dir = test_case.is_dir()
        paths = filter_files_by_patterns(test_case, self.claim_files, self.claimed_by_others_files)
        hints = []
        for path in paths:
            if is_dir:
                rel_path = path.relative_to(test_case)
                vocabulary.append(str(rel_path).encode())
                path_id = len(vocabulary) - 1
            else:
                path_id = None
            self._generate_hints_for_file(path, config, path_id, hints)
        return HintBundle(hints=hints, vocabulary=vocabulary)

    def _generate_hints_for_file(self, path: Path, config: Config, path_id: int | None, hints: list[Hint]) -> None:
        open_ch = ord(config.search.value[0])
        close_ch = ord(config.search.value[1])

        contents = path.read_bytes()
        prefixes = (
            [m.span() for m in re.finditer(config.search_prefix.encode(), contents)] if config.search_prefix else []
        )
        prefixes_pos = 0

        def get_touching_prefix(file_pos):
            nonlocal prefixes_pos
            while prefixes_pos < len(prefixes) and prefixes[prefixes_pos][1] < file_pos:
                prefixes_pos += 1
            if prefixes_pos < len(prefixes) and prefixes[prefixes_pos][1] == file_pos:
                return prefixes[prefixes_pos][0]
            return None

        def create_hint(start_pos, file_pos):
            if start_pos is None:
                return None
            match config.to_delete:
                case Deletion.ALL:
                    val = None
                    if config.replacement:
                        val = 0  # when config.replacement is used, the first string in the vocabulary points to it
                    p = Patch(left=start_pos, right=file_pos + 1, path=path_id, value=val)
                    return Hint(patches=(p,))
                case Deletion.ONLY:
                    return Hint(
                        patches=(
                            Patch(left=start_pos, right=start_pos + 1, path=path_id),
                            Patch(left=file_pos, right=file_pos + 1, path=path_id),
                        )
                    )
                case Deletion.INSIDE:
                    if file_pos - start_pos <= 1:
                        return None  # don't create an empty hint
                    return Hint(patches=(Patch(left=start_pos + 1, right=file_pos, path=path_id),))
                case _:
                    raise ValueError(f'Unexpected config {config}')

        # Scan the text left-to-right and maintain active (not yet matched) open brackets in a stack; None denotes a
        # "bad" open bracket - without the expected prefix.
        active_stack: list[int | None] = []
        for file_pos, ch in enumerate(contents):
            if ch == open_ch:
                start = get_touching_prefix(file_pos) if config.search_prefix else file_pos
                active_stack.append(start)
            elif ch == close_ch and active_stack:
                start_pos = active_stack.pop()
                if h := create_hint(start_pos, file_pos):
                    hints.append(h)

    def __get_config(self) -> Config:
        BalancedExpr = nestedmatcher.BalancedExpr
        match self.arg:
            case 'square-inside':
                return Config(search=BalancedExpr.squares, to_delete=Deletion.INSIDE)
            case 'angles-inside':
                return Config(search=BalancedExpr.angles, to_delete=Deletion.INSIDE)
            case 'parens-inside':
                return Config(search=BalancedExpr.parens, to_delete=Deletion.INSIDE)
            case 'curly-inside':
                return Config(search=BalancedExpr.curlies, to_delete=Deletion.INSIDE)
            case 'square':
                return Config(search=BalancedExpr.squares, to_delete=Deletion.ALL)
            case 'angles':
                return Config(search=BalancedExpr.angles, to_delete=Deletion.ALL)
            case 'parens-to-zero':
                return Config(search=BalancedExpr.parens, to_delete=Deletion.ALL, replacement='0')
            case 'parens':
                return Config(search=BalancedExpr.parens, to_delete=Deletion.ALL)
            case 'curly':
                return Config(search=BalancedExpr.curlies, to_delete=Deletion.ALL)
            case 'curly2':
                return Config(search=BalancedExpr.curlies, to_delete=Deletion.ALL, replacement=';')
            case 'curly3':
                return Config(search=BalancedExpr.curlies, to_delete=Deletion.ALL, search_prefix=r'=\s*')
            case 'parens-only':
                return Config(search=BalancedExpr.parens, to_delete=Deletion.ONLY)
            case 'curly-only':
                return Config(search=BalancedExpr.curlies, to_delete=Deletion.ONLY)
            case 'angles-only':
                return Config(search=BalancedExpr.angles, to_delete=Deletion.ONLY)
            case 'square-only':
                return Config(search=BalancedExpr.squares, to_delete=Deletion.ONLY)
            case _:
                raise UnknownArgumentError(self.__class__.__name__, self.arg)

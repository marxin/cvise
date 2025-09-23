from enum import Enum, auto, unique
from dataclasses import dataclass
from pathlib import Path
import re
from typing import List, Optional, Union

from cvise.passes.hint_based import HintBasedPass
from cvise.utils import nestedmatcher
from cvise.utils.error import UnknownArgumentError
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

        hints = []
        if test_case.is_dir():
            for path in test_case.rglob('*'):
                if not path.is_dir() and not path.is_symlink():
                    rel_path = path.relative_to(test_case)
                    vocabulary.append(str(rel_path).encode())
                    file_id = len(vocabulary) - 1
                    self._generate_hints_for_file(path, config, file_id, hints)
        else:
            self._generate_hints_for_file(test_case, config, file_id=None, hints=hints)
        return HintBundle(hints=hints, vocabulary=vocabulary)

    def _generate_hints_for_file(self, path: Path, config: Config, file_id: Optional[int], hints: List[Hint]):
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
            if config.to_delete == Deletion.ALL:
                p = Patch(left=start_pos, right=file_pos + 1, file=file_id)
                if config.replacement:
                    p.value = 0  # when config.replacement is used, the first string in the vocabulary points to it
                return Hint(patches=[p])
            if config.to_delete == Deletion.ONLY:
                return Hint(
                    patches=[
                        Patch(left=start_pos, right=start_pos + 1, file=file_id),
                        Patch(left=file_pos, right=file_pos + 1, file=file_id),
                    ]
                )
            if config.to_delete == Deletion.INSIDE:
                if file_pos - start_pos <= 1:
                    return None  # don't create an empty hint
                return Hint(patches=[Patch(left=start_pos + 1, right=file_pos, file=file_id)])
            raise ValueError(f'Unexpected config {config}')

        # Scan the text left-to-right and maintain active (not yet matched) open brackets in a stack; None denotes a
        # "bad" open bracket - without the expected prefix.
        active_stack: List[Union[int, None]] = []
        for file_pos, ch in enumerate(contents):
            if ch == open_ch:
                start = get_touching_prefix(file_pos) if config.search_prefix else file_pos
                active_stack.append(start)
            elif ch == close_ch and active_stack:
                start_pos = active_stack.pop()
                if h := create_hint(start_pos, file_pos):
                    hints.append(h)

    def __get_config(self):
        BalancedExpr = nestedmatcher.BalancedExpr
        if self.arg == 'square-inside':
            return Config(search=BalancedExpr.squares, to_delete=Deletion.INSIDE)
        if self.arg == 'angles-inside':
            return Config(search=BalancedExpr.angles, to_delete=Deletion.INSIDE)
        if self.arg == 'parens-inside':
            return Config(search=BalancedExpr.parens, to_delete=Deletion.INSIDE)
        if self.arg == 'curly-inside':
            return Config(search=BalancedExpr.curlies, to_delete=Deletion.INSIDE)
        if self.arg == 'square':
            return Config(search=BalancedExpr.squares, to_delete=Deletion.ALL)
        if self.arg == 'angles':
            return Config(search=BalancedExpr.angles, to_delete=Deletion.ALL)
        if self.arg == 'parens-to-zero':
            return Config(search=BalancedExpr.parens, to_delete=Deletion.ALL, replacement='0')
        if self.arg == 'parens':
            return Config(search=BalancedExpr.parens, to_delete=Deletion.ALL)
        if self.arg == 'curly':
            return Config(search=BalancedExpr.curlies, to_delete=Deletion.ALL)
        if self.arg == 'curly2':
            return Config(search=BalancedExpr.curlies, to_delete=Deletion.ALL, replacement=';')
        if self.arg == 'curly3':
            return Config(search=BalancedExpr.curlies, to_delete=Deletion.ALL, search_prefix=r'=\s*')
        if self.arg == 'parens-only':
            return Config(search=BalancedExpr.parens, to_delete=Deletion.ONLY)
        if self.arg == 'curly-only':
            return Config(search=BalancedExpr.curlies, to_delete=Deletion.ONLY)
        if self.arg == 'angles-only':
            return Config(search=BalancedExpr.angles, to_delete=Deletion.ONLY)
        if self.arg == 'square-only':
            return Config(search=BalancedExpr.squares, to_delete=Deletion.ONLY)
        raise UnknownArgumentError(self.__class__.__name__, self.arg)

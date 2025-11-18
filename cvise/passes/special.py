import re
from collections.abc import Callable
from pathlib import Path

from cvise.passes.abstract import AbstractPass, PassResult
from cvise.utils.error import UnknownArgumentError


class SpecialPass(AbstractPass):
    def check_prerequisites(self):
        return True

    def __get_config(self):
        config: dict[str, str | Callable | None] = {
            'search': None,
            'replace_fn': None,
        }

        def replace_printf(m):
            return r"printf('%d\n', (int){})".format(m.group('list').split(',')[0])

        def replace_empty(m):
            return ''

        match self.arg:
            case 'a':
                config['search'] = r'transparent_crc\s*\((?P<list>[^)]*)\)'
                config['replace_fn'] = replace_printf
            case 'b':
                config['search'] = r"extern 'C'"
                config['replace_fn'] = replace_empty
            case 'c':
                config['search'] = r"extern 'C\+\+'"
                config['replace_fn'] = replace_empty
            case _:
                raise UnknownArgumentError(self.__class__.__name__, self.arg)

        return config

    def __get_next_match(self, test_case: Path, pos):
        prog = test_case.read_text()

        config = self.__get_config()
        pattern = config['search']
        assert isinstance(pattern, str)

        regex = re.compile(pattern, flags=re.DOTALL)
        m = regex.search(prog, pos=pos)

        return m

    def new(self, test_case: Path, *args, **kwargs):
        config = self.__get_config()
        pattern = config['search']
        assert isinstance(pattern, str)
        replace_fn = config['replace_fn']
        assert isinstance(replace_fn, Callable)

        prog = test_case.read_text()
        regex = re.compile(pattern, flags=re.DOTALL)
        modifications = list(reversed([(m.span(), replace_fn(m)) for m in regex.finditer(prog)]))
        if not modifications:
            return None
        return {'modifications': modifications, 'index': 0}

    def advance(self, test_case: Path, state):
        state = state.copy()
        state['index'] += 1
        if state['index'] >= len(state['modifications']):
            return None
        return state

    def advance_on_success(self, test_case: Path, state, *args, **kwargs):
        return self.new(test_case)

    def transform(self, test_case: Path, state, *args, **kwargs):
        data = test_case.read_text()
        index = state['index']
        ((start, end), replacement) = state['modifications'][index]
        new_data = data[:start] + replacement + data[end:]
        test_case.write_text(new_data)
        return (PassResult.OK, state)

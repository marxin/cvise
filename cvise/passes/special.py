from pathlib import Path
import re

from cvise.passes.abstract import AbstractPass, PassResult
from cvise.utils.error import UnknownArgumentError


class SpecialPass(AbstractPass):
    def check_prerequisites(self):
        return True

    def __get_config(self):
        config = {
            'search': None,
            'replace_fn': None,
        }

        def replace_printf(m):
            return r"printf('%d\n', (int){})".format(m.group('list').split(',')[0])

        def replace_empty(m):
            return ''

        if self.arg == 'a':
            config['search'] = r'transparent_crc\s*\((?P<list>[^)]*)\)'
            config['replace_fn'] = replace_printf
        elif self.arg == 'b':
            config['search'] = r"extern 'C'"
            config['replace_fn'] = replace_empty
        elif self.arg == 'c':
            config['search'] = r"extern 'C\+\+'"
            config['replace_fn'] = replace_empty
        else:
            raise UnknownArgumentError(self.__class__.__name__, self.arg)

        return config

    def __get_next_match(self, test_case: Path, pos):
        with open(test_case) as in_file:
            prog = in_file.read()

        config = self.__get_config()
        regex = re.compile(config['search'], flags=re.DOTALL)
        m = regex.search(prog, pos=pos)

        return m

    def new(self, test_case: Path, *args, **kwargs):
        config = self.__get_config()
        with open(test_case) as in_file:
            prog = in_file.read()
            regex = re.compile(config['search'], flags=re.DOTALL)
            modifications = list(reversed([(m.span(), config['replace_fn'](m)) for m in regex.finditer(prog)]))
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

    def transform(self, test_case: Path, state, process_event_notifier):
        with open(test_case) as in_file:
            data = in_file.read()
            index = state['index']
            ((start, end), replacement) = state['modifications'][index]
            new_data = data[:start] + replacement + data[end:]
            with open(test_case, 'w') as out_file:
                out_file.write(new_data)
                return (PassResult.OK, state)

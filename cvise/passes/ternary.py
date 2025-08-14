from pathlib import Path

from cvise.passes.abstract import AbstractPass, PassResult
from cvise.utils import nestedmatcher
from cvise.utils.error import UnknownArgumentError


class TernaryPass(AbstractPass):
    varnum = r'(?:[-+]?[0-9a-zA-Z\_]+)'
    border = r'[*{([:,})\];]'
    border_or_space = r'(?:(?:' + border + r')|\s)'
    border_or_space_pattern = nestedmatcher.RegExPattern(border_or_space)
    varnum_pattern = nestedmatcher.RegExPattern(varnum)
    balanced_parens_pattern = nestedmatcher.BalancedPattern(nestedmatcher.BalancedExpr.parens)
    varnumexp_pattern = nestedmatcher.OrPattern(varnum_pattern, balanced_parens_pattern)

    parts = [
        (border_or_space_pattern, 'del1'),
        varnumexp_pattern,
        nestedmatcher.RegExPattern(r'\s*\?\s*'),
        (varnumexp_pattern, 'b'),
        nestedmatcher.RegExPattern(r'\s*:\s*'),
        (varnumexp_pattern, 'c'),
        (border_or_space_pattern, 'del2'),
    ]

    def check_prerequisites(self):
        return True

    def __get_next_match(self, test_case: Path, pos):
        prog = test_case.read_text()
        m = nestedmatcher.search(self.parts, prog, pos=pos)
        return m

    def new(self, test_case: Path, *args, **kwargs):
        return self.__get_next_match(test_case, pos=0)

    def advance(self, test_case: Path, state):
        return self.__get_next_match(test_case, pos=state['all'][0] + 1)

    def advance_on_success(self, test_case: Path, state, *args, **kwargs):
        return self.__get_next_match(test_case, pos=state['all'][0])

    def transform(self, test_case: Path, state, process_event_notifier):
        prog = test_case.read_text()
        prog2 = prog

        while True:
            if state is None:
                return (PassResult.STOP, state)
            else:
                if self.arg not in ['b', 'c']:
                    raise UnknownArgumentError(self.__class__.__name__, self.arg)

                prog2 = (
                    prog2[0 : state['del1'][1]]
                    + prog2[state[self.arg][0] : state[self.arg][1]]
                    + prog2[state['del2'][0] :]
                )

                if prog != prog2:
                    test_case.write_text(prog2)
                    return (PassResult.OK, state)
                else:
                    state = self.advance(test_case, state)

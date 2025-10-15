import re
import tempfile
from pathlib import Path
from typing import Optional

from cvise.passes.abstract import AbstractPass, BinaryState, PassResult


class IfPass(AbstractPass):
    line_regex = re.compile('^\\s*#\\s*if')

    def __init__(self, external_programs: dict[str, Optional[str]], **kwargs):
        super().__init__(external_programs=external_programs, **kwargs)

    def check_prerequisites(self):
        return self.check_external_program('unifdef')

    @staticmethod
    def __macro_continues(line):
        return line.rstrip().endswith('\\')

    def __count_instances(self, test_case: Path):
        count = 0
        in_multiline = False
        with open(test_case) as in_file:
            for line in in_file.readlines():
                if in_multiline:
                    if self.__macro_continues(line):
                        continue
                    else:
                        in_multiline = False

                if self.line_regex.search(line):
                    count += 1
                    if self.__macro_continues(line):
                        in_multiline = True
        return count

    def new(self, test_case: Path, *args, **kwargs):
        bs = BinaryState.create(self.__count_instances(test_case))
        if bs:
            bs.value = 0  # type: ignore
        return bs

    def advance(self, test_case: Path, state):
        if state.value == 0:
            state = state.copy()
            state.value = 1
        else:
            state = state.advance()
            if state:
                state.value = 0
        return state

    def advance_on_success(self, test_case: Path, state, *args, **kwargs):
        return state.advance_on_success(self.__count_instances(test_case))

    def transform(self, test_case: Path, state, process_event_notifier, *args, **kwargs):
        with tempfile.NamedTemporaryFile(mode='w+', delete=False, dir=test_case.parent) as tmp_file:
            with open(test_case) as in_file:
                i = 0
                in_multiline = False
                for line in in_file.readlines():
                    if in_multiline:
                        if self.__macro_continues(line):
                            continue
                        else:
                            in_multiline = False

                    if self.line_regex.search(line):
                        if state.index <= i and i < state.end():
                            if self.__macro_continues(line):
                                in_multiline = True
                            line = f'#if {state.value}\n'
                        i += 1
                    tmp_file.write(line)

        cmd = [
            self.external_programs['unifdef'],
            '-B',
            '-x',
            '2',
            '-k',
            '-o',
            str(test_case),
            tmp_file.name,
        ]
        _stdout, _stderr, returncode = process_event_notifier.run_process(cmd)
        if returncode != 0:
            return (PassResult.ERROR, state)
        else:
            return (PassResult.OK, state)

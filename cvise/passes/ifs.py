import os
import re
import tempfile

from cvise.passes.abstract import AbstractPass, BinaryState, PassResult


class IfPass(AbstractPass):
    line_regex = re.compile('^\\s*#\\s*if')

    def check_prerequisites(self):
        return self.check_external_program('unifdef')

    @staticmethod
    def __macro_continues(line):
        return line.rstrip().endswith('\\')

    def __count_instances(self, test_case):
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

    def new(self, test_case, _=None):
        bs = BinaryState.create(self.__count_instances(test_case))
        if bs:
            bs.value = 0
        return bs

    def advance(self, test_case, state):
        if state.value == 0:
            state = state.copy()
            state.value = 1
        else:
            state = state.advance()
            if state:
                state.value = 0
        return state

    def advance_on_success(self, test_case, state):
        return state.advance_on_success(self.__count_instances(test_case))

    def transform(self, test_case, state, process_event_notifier):
        tmp = os.path.dirname(test_case)
        with tempfile.NamedTemporaryFile(mode='w+', delete=False, dir=tmp) as tmp_file:
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

        cmd = [self.external_programs['unifdef'], '-B', '-x', '2', '-k', '-o', test_case, tmp_file.name]
        stdout, stderr, returncode = process_event_notifier.run_process(cmd)
        if returncode != 0:
            return (PassResult.ERROR, state)
        else:
            return (PassResult.OK, state)

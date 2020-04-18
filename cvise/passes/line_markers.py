import logging
import shutil
import subprocess
import tempfile
import re
import os

from cvise.passes.abstract import AbstractPass, BinaryState, PassResult

class LineMarkersPass(AbstractPass):
    line_regex = re.compile('^\\s*#\\s*[0-9]+')

    def check_prerequisites(self):
        return True

    def __count_instances(self, test_case):
        count = 0
        with open(test_case, "r") as in_file:
            for line in in_file.readlines():
                if self.line_regex.search(line):
                    count += 1
        return count

    def new(self, test_case):
        return BinaryState.create(self.__count_instances(test_case))

    def advance(self, test_case, state):
        return state.advance()

    def advance_on_success(self, test_case, state):
        return state.advance_on_success(self.__count_instances(test_case))

    def transform(self, test_case, state):
        tmp = os.path.dirname(test_case)
        with tempfile.NamedTemporaryFile(mode="w+", delete=False, dir=tmp) as tmp_file:
            with open(test_case, "r") as in_file:
                i = 0
                for line in in_file.readlines():
                    if self.line_regex.search(line):
                        if i < state.index or i >= state.end():
                            tmp_file.write(line)
                        i += 1
                    else:
                        tmp_file.write(line)

        shutil.move(tmp_file.name, test_case)
        return (PassResult.OK, state)

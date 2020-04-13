import os
import re
import shutil
import tempfile

from creduce.passes.abstract import AbstractPass, PassResult

class BlankPass(AbstractPass):
    def check_prerequisites(self):
        return True

    def new(self, test_case):
        return 0

    def advance(self, test_case, state):
        return state + 1

    def advance_on_success(self, test_case, state):
        return state

    @staticmethod
    def __transform(test_case, pattern):
        tmp = os.path.dirname(test_case)
        with tempfile.NamedTemporaryFile(mode="w+", delete=False, dir=tmp) as tmp_file:
            with open(test_case, "r") as in_file:
                matched = False

                for l in in_file:
                    if re.match(pattern, l) is not None:
                        matched = True
                    else:
                        tmp_file.write(l)

        if matched:
            shutil.move(tmp_file.name, test_case)
        else:
            os.unlink(tmp_file.name)

        return matched

    def transform(self, test_case, state):
        patterns = [r"^\s*$", r"^#"]

        if state >= len(patterns):
            return (PassResult.STOP, state)
        else:
            success = False

            while not success and state < len(patterns):
                success = self.__transform(test_case, patterns[state])
                state += 1

            return (PassResult.OK if success else PassResult.STOP, state)

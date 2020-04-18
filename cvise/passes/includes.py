import os
import re
import shutil
import tempfile

from cvise.passes.abstract import AbstractPass, PassResult

class IncludesPass(AbstractPass):
    def check_prerequisites(self):
        return True

    def new(self, test_case):
        return 1

    def advance(self, test_case, state):
        return state + 1

    def advance_on_success(self, test_case, state):
        return state

    def transform(self, test_case, state):
        tmp = os.path.dirname(test_case)
        with tempfile.NamedTemporaryFile(mode="w+", delete=False, dir=tmp) as tmp_file:
            with open(test_case, "r") as in_file:
                includes = 0
                matched = False

                for line in in_file:
                    include_match = re.match(r"\s*#\s*include", line)

                    if include_match is not None:
                        includes += 1

                        if includes == state:
                            matched = True
                            # Go to next include
                            # Don't write the original line back to file
                            continue

                    tmp_file.write(line)

        if matched:
            shutil.move(tmp_file.name, test_case)
            return (PassResult.OK, state)
        else:
            os.unlink(tmp_file.name)
            return (PassResult.STOP, state)

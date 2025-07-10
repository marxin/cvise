import os
import re
import shutil
import tempfile

from cvise.passes.abstract import AbstractPass, PassResult


class IncludeIncludesPass(AbstractPass):
    def check_prerequisites(self):
        return True

    def new(self, test_case, **kwargs):
        return 1

    def advance(self, test_case, state):
        return state + 1

    def advance_on_success(self, test_case, state, **kwargs):
        return state

    def transform(self, test_case, state, process_event_notifier):
        with open(test_case) as in_file:
            tmp = os.path.dirname(test_case)
            with tempfile.NamedTemporaryFile(mode='w+', delete=False, dir=tmp) as tmp_file:
                includes = 0
                matched = False

                for line in in_file:
                    include_match = re.match(r"\s*#\s*include\s*'(.*?)'", line)

                    if include_match is not None:
                        includes += 1

                        if includes == state:
                            try:
                                with open(include_match.group(1)) as inc_file:
                                    matched = True
                                    tmp_file.write(inc_file.read())
                                    # Go to next include
                                    # Don't write original line back to file
                                    continue
                            except FileNotFoundError:
                                # Do nothing. The original line will be written back
                                pass

                    tmp_file.write(line)

        if matched:
            shutil.move(tmp_file.name, test_case)
            return (PassResult.OK, state)
        else:
            os.unlink(tmp_file.name)
            return (PassResult.STOP, state)

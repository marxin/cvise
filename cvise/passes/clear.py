import os
import shutil
import tempfile

from cvise.passes.abstract import AbstractPass, PassResult


class ClearPass(AbstractPass):
    def check_prerequisites(self):
        return True

    def new(self, test_case, _=None):
        return 0

    def advance(self, test_case, state):
        return state + 1

    def advance_on_success(self, test_case, state):
        return state

    @staticmethod
    def __transform(test_case):
        if os.path.getsize(test_case) == 0:
            return False
        tmp = os.path.dirname(test_case)
        tmp_file = tempfile.NamedTemporaryFile(mode='w+', delete=False, dir=tmp)
        shutil.move(tmp_file.name, test_case)
        return True

    def transform(self, test_case, state, process_event_notifier):
        return (PassResult.OK if self.__transform(test_case) else PassResult.STOP, state)

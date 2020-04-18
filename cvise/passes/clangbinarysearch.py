import logging
import math
import os
import re
import shutil
import subprocess
import tempfile

from cvise.passes.abstract import AbstractPass, BinaryState, PassResult
from cvise.utils import compat

class ClangBinarySearchPass(AbstractPass):
    def check_prerequisites(self):
        return shutil.which(self.external_programs["clang_delta"]) is not None

    def new(self, test_case):
        return BinaryState.create(self.__count_instances(test_case))

    def advance(self, test_case, state):
        return state.advance()

    def advance_on_success(self, test_case, state):
        return state.advance_on_success(self.__count_instances(test_case))

    def __count_instances(self, test_case):
        cmd = [self.external_programs["clang_delta"], "--query-instances={}".format(self.arg), test_case]

        try:
            proc = compat.subprocess_run(cmd, universal_newlines=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        except subprocess.SubprocessError:
            return 0

        m = re.match("Available transformation instances: ([0-9]+)$", proc.stdout)

        if m is None:
            return 0
        else:
            return int(m.group(1))

    def transform(self, test_case, state):
        logging.debug("TRANSFORM: index = {}, chunk = {}, instances = {}".format(state.index, state.chunk, state.instances))

        tmp = os.path.dirname(test_case)
        with tempfile.NamedTemporaryFile(delete=False, dir=tmp) as tmp_file:
            cmd = [self.external_programs["clang_delta"], "--transformation={}".format(self.arg), "--counter={}".format(state.index + 1), "--to-counter={}".format(state.end()), test_case]
            logging.debug(" ".join(cmd))

            try:
                proc = compat.subprocess_run(cmd, universal_newlines=True, stdout=tmp_file, stderr=subprocess.PIPE)
            except subprocess.SubprocessError:
                return (PassResult.ERROR, state)

        if proc.returncode == 0:
            shutil.move(tmp_file.name, test_case)
            return (PassResult.OK, state)
        else:
            os.unlink(tmp_file.name)
            return (PassResult.STOP if proc.returncode == 255 else PassResult.ERROR, state)

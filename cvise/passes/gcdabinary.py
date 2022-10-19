import logging
import os
import shutil
import subprocess
import tempfile

from cvise.passes.abstract import AbstractPass, BinaryState, PassResult


class GCDABinaryPass(AbstractPass):
    def check_prerequisites(self):
        return self.check_external_program('gcov-dump')

    def __create_state(self, test_case):
        try:
            proc = subprocess.run([self.external_programs['gcov-dump'], '-p', test_case], encoding='utf8', timeout=1,
                                  stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            if proc.returncode != 0:
                logging.warning(f'gcov-dump -p failed: {proc.stderr}')
                return None
            functions = []
            for line in proc.stdout.splitlines():
                parts = line.split(':')
                if 'FUNCTION' in line and len(parts) >= 5:
                    functions.append(int(parts[1]))

            state = BinaryState.create(len(functions))
            if state:
                state.functions = functions
            return state
        except subprocess.SubprocessError as e:
            logging.warning(f'gcov-dump -p failed: {e}')
            return None

    def new(self, test_case, check_sanity=None):
        return self.__create_state(test_case)

    def advance(self, test_case, state):
        return state.advance()

    def advance_on_success(self, test_case, state):
        return self.__create_state(test_case)

    def transform(self, test_case, state, process_event_notifier):
        data = open(test_case, 'rb').read()
        old_len = len(data)
        newdata = data[0:state.functions[state.index]]
        if state.end() < len(state.functions):
            newdata += data[state.functions[state.end()]:]
        assert len(newdata) < old_len

        tmp = os.path.dirname(test_case)
        with tempfile.NamedTemporaryFile(mode='wb', delete=False, dir=tmp) as tmp_file:
            tmp_file.write(newdata)

        shutil.move(tmp_file.name, test_case)
        return (PassResult.OK, state)

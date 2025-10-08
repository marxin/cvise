import logging
from pathlib import Path
import subprocess
from typing import Dict, Optional

from cvise.passes.abstract import AbstractPass, BinaryState, PassResult


class GCDABinaryPass(AbstractPass):
    def __init__(self, external_programs: Dict[str, Optional[str]], **kwargs):
        super().__init__(external_programs=external_programs, **kwargs)

    def check_prerequisites(self):
        return self.check_external_program('gcov-dump')

    def __create_state(self, test_case: Path):
        try:
            proc = subprocess.run(
                [self.external_programs['gcov-dump'], '-p', str(test_case)],
                encoding='utf8',
                timeout=1,
                capture_output=True,
            )
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

    def new(self, test_case: Path, *args, **kwargs):
        return self.__create_state(test_case)

    def advance(self, test_case: Path, state):
        return state.advance()

    def advance_on_success(self, test_case: Path, state, *args, **kwargs):
        return self.__create_state(test_case)

    def transform(self, test_case: Path, state, *args, **kwargs):
        data = test_case.read_bytes()
        old_len = len(data)
        newdata = data[0 : state.functions[state.index]]
        if state.end() < len(state.functions):
            newdata += data[state.functions[state.end()] :]
        assert len(newdata) < old_len

        test_case.write_bytes(newdata)
        return (PassResult.OK, state)

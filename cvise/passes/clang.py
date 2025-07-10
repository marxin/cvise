import logging
import os
import shutil

from cvise.passes.abstract import AbstractPass, PassResult
from cvise.utils.misc import CloseableTemporaryFile


class ClangPass(AbstractPass):
    def check_prerequisites(self):
        return self.check_external_program('clang_delta')

    def new(self, test_case, **kwargs):
        return 1

    def advance(self, test_case, state):
        return state + 1

    def advance_on_success(self, test_case, state, **kwargs):
        return state

    def transform(self, test_case, state, process_event_notifier):
        tmp = os.path.dirname(test_case)
        with CloseableTemporaryFile(mode='w', dir=tmp) as tmp_file:
            args = [
                self.external_programs['clang_delta'],
                f'--transformation={self.arg}',
                f'--counter={state}',
            ]
            if self.user_clang_delta_std:
                args.append(f'--std={self.user_clang_delta_std}')
            cmd = args + [test_case]

            logging.debug(' '.join(cmd))

            stdout, _, returncode = process_event_notifier.run_process(cmd)
            if returncode == 0:
                tmp_file.write(stdout)
                tmp_file.close()
                shutil.copy(tmp_file.name, test_case)
                return (PassResult.OK, state)
            else:
                if returncode == 255 or returncode == 1:
                    return (PassResult.STOP, state)
                else:
                    return (PassResult.ERROR, state)

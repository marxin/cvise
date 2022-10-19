import copy
from enum import auto, Enum, unique
import logging
import shutil
import subprocess


@unique
class PassResult(Enum):
    OK = auto()
    INVALID = auto()
    STOP = auto()
    ERROR = auto()


class BinaryState:
    def __init__(self):
        pass

    def __repr__(self):
        return 'BinaryState: %d-%d of %d instances' % (self.index, self.end(), self.instances)

    @staticmethod
    def create(instances):
        if not instances:
            return None
        self = BinaryState()
        self.instances = instances
        self.chunk = instances
        self.index = 0
        return self

    def copy(self):
        return copy.copy(self)

    def end(self):
        return min(self.index + self.chunk, self.instances)

    def real_chunk(self):
        return self.end() - self.index

    def advance(self):
        self = self.copy()
        original_index = self.index
        self.index += self.chunk
        if self.index >= self.instances:
            self.chunk = int(self.chunk / 2)
            if self.chunk < 1:
                return None
            logging.debug(f'granularity reduced to {self.chunk}')
            self.index = 0
        else:
            logging.debug(f'***ADVANCE*** from {original_index} to {self.index} with chunk {self.chunk}')
        return self

    def advance_on_success(self, instances):
        if not instances:
            return None
        self.instances = instances
        if self.index >= self.instances:
            return self.advance()
        else:
            return self


class AbstractPass:
    @unique
    class Option(Enum):
        slow = 'slow'
        windows = 'windows'

    def __init__(self, arg=None, external_programs=None):
        self.external_programs = external_programs
        self.arg = arg

    def __repr__(self):
        if self.arg is not None:
            return f'{type(self).__name__}::{self.arg}'
        else:
            return f'{type(self).__name__}'

    def check_external_program(self, name):
        program = self.external_programs[name]
        if not program:
            return False
        result = shutil.which(program) is not None
        if not result:
            logging.error(f'cannot find external program {name}')
        return result

    def check_prerequisites(self):
        raise NotImplementedError(f"Class {type(self).__name__} has not implemented 'check_prerequisites'!")

    def new(self, test_case, check_sanity):
        raise NotImplementedError(f"Class {type(self).__name__} has not implemented 'new'!")

    def advance(self, test_case, state):
        raise NotImplementedError(f"Class {type(self).__name__} has not implemented 'advance'!")

    def advance_on_success(self, test_case, state):
        raise NotImplementedError(f"Class {type(self).__name__} has not implemented 'advance_on_success'!")

    def transform(self, test_case, state, process_event_notifier):
        raise NotImplementedError(f"Class {type(self).__name__} has not implemented 'transform'!")


@unique
class ProcessEventType(Enum):
    STARTED = auto()
    FINISHED = auto()


class ProcessEvent:
    def __init__(self, pid, event_type):
        self.pid = pid
        self.type = event_type


class ProcessEventNotifier:
    def __init__(self, pid_queue):
        self.pid_queue = pid_queue

    def run_process(self, cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=False):
        if shell:
            assert isinstance(cmd, str)
        proc = subprocess.Popen(cmd, stdout=stdout, stderr=stderr, universal_newlines=True, encoding='utf8', shell=shell)
        if self.pid_queue:
            self.pid_queue.put(ProcessEvent(proc.pid, ProcessEventType.STARTED))
        stdout, stderr = proc.communicate()
        if self.pid_queue:
            self.pid_queue.put(ProcessEvent(proc.pid, ProcessEventType.FINISHED))
        return (stdout, stderr, proc.returncode)

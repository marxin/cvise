import re
import enum
import logging
import copy
import subprocess

from enum import Enum, auto

@enum.unique
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

    def advance(self):
        self = self.copy()
        original_index = self.index
        self.index += self.chunk
        if self.index >= self.instances:
            self.chunk = int(self.chunk / 2)
            if self.chunk <= 1:
                return None
            logging.debug("granularity reduced to {}".format(self.chunk))
            self.index = 0
        else:
            logging.debug("***ADVANCE*** from {} to {} with chunk {}".format(original_index, self.index, self.chunk))
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
    @enum.unique
    class Option(enum.Enum):
        slow = "slow"
        windows = "windows"

    def __init__(self, arg=None, external_programs=None):
        self.external_programs = external_programs
        self.arg = arg

    def __repr__(self):
        if self.arg is not None:
            return "{}::{}".format(type(self).__name__, self.arg)
        else:
            return "{}".format(type(self).__name__)

    def check_prerequisites(self):
        raise NotImplementedError("Class {} has not implemented 'check_prerequisites'!".format(type(self).__name__))

    def new(self, test_case):
        raise NotImplementedError("Class {} has not implemented 'new'!".format(type(self).__name__))

    def advance(self, test_case, state):
        raise NotImplementedError("Class {} has not implemented 'advance'!".format(type(self).__name__))

    def advance_on_success(self, test_case, state):
        raise NotImplementedError("Class {} has not implemented 'advance_on_success'!".format(type(self).__name__))

    def transform(self, test_case, state, process_event_notifier):
        raise NotImplementedError("Class {} has not implemented 'transform'!".format(type(self).__name__))

@enum.unique
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

    def run_process(self, cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE):
        proc = subprocess.Popen(cmd, stdout=stdout, stderr=stderr, universal_newlines=True, encoding='utf8')
        if self.pid_queue:
            self.pid_queue.put(ProcessEvent(proc.pid, ProcessEventType.STARTED))
        stdout, stderr = proc.communicate()
        if self.pid_queue:
            self.pid_queue.put(ProcessEvent(proc.pid, ProcessEventType.FINISHED))
        return (stdout, stderr, proc.returncode)

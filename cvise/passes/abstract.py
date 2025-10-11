from __future__ import annotations
import copy
from dataclasses import dataclass
from enum import auto, Enum, unique
import logging
from pathlib import Path
import random
import shutil
from typing import Any

from cvise.utils.process import ProcessEventNotifier


@unique
class PassResult(Enum):
    OK = auto()
    INVALID = auto()
    STOP = auto()
    ERROR = auto()


@dataclass(frozen=True)
class SubsegmentState:
    """Iterates over subsegments of the given instances, with at most the given chunk size.

    Essentially enumerates all ranges of hints of the form [i; i+j), for j=1..max_chunk, i=0..N-j.
    For each chunk size j, it begins from a random position: i=start, then i=start+1, etc., until it makes a "wrapover"
    to i=0, i=1, ..., until i=start-1; after that, the same is done with the chunk size j+1, and so on.
    """

    instances: int
    chunk: int
    max_chunk: int
    index: int
    start: int

    def __repr__(self):
        return f'SubsegmentState({self.compact_repr()})'

    def compact_repr(self) -> str:
        return f'{self.index}-{self.end()} out of {self.instances}'

    @staticmethod
    def create(instances: int, min_chunk: int, max_chunk: int):
        assert min_chunk > 0
        if min_chunk > instances or min_chunk > max_chunk:
            return None
        start = random.randint(0, instances - min_chunk)
        return SubsegmentState(instances, chunk=min_chunk, max_chunk=max_chunk, index=start, start=start)

    def end(self) -> int:
        return self.index + self.chunk

    def real_chunk(self) -> int:
        return self.chunk

    def advance(self) -> SubsegmentState | None:
        to_start = self.index + 1 == self.start
        to_wrapover = self.index + 1 + self.chunk > self.instances
        if to_start or (to_wrapover and self.start == 0):
            return SubsegmentState.create(self.instances, self.chunk + 1, self.max_chunk)
        return SubsegmentState(
            instances=self.instances,
            chunk=self.chunk,
            max_chunk=self.max_chunk,
            index=0 if to_wrapover else self.index + 1,
            start=self.start,
        )

    def advance_on_success(self, instances) -> SubsegmentState | None:
        if self.chunk > instances:
            return None
        if wrapover := self.index + self.chunk > instances:
            wrapover_to_start = self.index < self.start or self.start == 0
            if wrapover_to_start:
                return SubsegmentState.create(instances, self.chunk + 1, self.max_chunk)
        return SubsegmentState(
            instances=instances,
            chunk=self.chunk,
            max_chunk=self.max_chunk,
            index=0 if wrapover else self.index,
            start=0 if self.start + self.chunk > instances else self.start,
        )


class BinaryState:
    def __init__(self, instances: int, chunk: int, index: int):
        self.instances: int = instances
        self.chunk: int = chunk
        self.index: int = index

    def __repr__(self):
        return f'BinaryState({self.index}-{self.end()}, {self.instances} instances, step: {self.chunk})'

    def compact_repr(self) -> str:
        return f'{self.index}-{self.end()} out of {self.instances} with step {self.chunk}'

    # FIXME: Remove this and __hash__ in favor of dataclass, once all passes and this class are updated to not
    # modify/add properties.
    def __eq__(self, other):
        return isinstance(other, BinaryState) and self._key() == other._key()

    def __hash__(self):
        return hash(self._key())

    def _key(self):
        return (self.instances, self.chunk, self.index)

    @staticmethod
    def create(instances):
        if not instances:
            return None
        return BinaryState(instances, chunk=instances, index=0)

    def copy(self):
        return copy.copy(self)

    def end(self):
        return min(self.index + self.chunk, self.instances)

    def real_chunk(self):
        return self.end() - self.index

    def advance(self):
        self = self.copy()
        self.index += self.chunk
        if self.index >= self.instances:
            self.chunk = int(self.chunk / 2)
            if self.chunk < 1:
                return None
            logging.debug(f'granularity reduced to {self.chunk}')
            self.index = 0
        else:
            logging.debug(f'***ADVANCE*** to {self}')
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

    def __init__(
        self,
        arg: str | None = None,
        external_programs: dict[str, str | None] | None = None,
        max_transforms: int | None = None,
        claim_files: list[str] | None = None,
        claimed_by_others_files: list[str] | None = None,
        *args,
        **kwargs,
    ):
        self.arg = arg
        self.external_programs = external_programs
        self.max_transforms = max_transforms
        self.claim_files = claim_files or []
        self.claimed_by_others_files = claimed_by_others_files or []

    def __repr__(self):
        if self.arg is not None:
            name = f'{type(self).__name__}::{self.arg}'
        else:
            name = f'{type(self).__name__}'

        if self.max_transforms is not None:
            name += f' ({self.max_transforms} T)'
        return name

    def check_external_program(self, name) -> bool:
        program = self.external_programs[name]
        if not program:
            return False
        result = shutil.which(program) is not None
        if not result:
            logging.error(f'cannot find external program {name}')
        return result

    def check_prerequisites(self):
        raise NotImplementedError(f"Class {type(self).__name__} has not implemented 'check_prerequisites'!")

    def user_visible_name(self) -> str:
        """The name under which the pass should be mentioned (in logs, stats, etc.).

        Useful for overriding by subclasses that are "subordinate" to high-level passes.
        """
        return repr(self)

    def supports_dir_test_cases(self) -> bool:
        """Whether the pass supports input test cases that are directories (as opposed to single files).

        By default false; intended to be overridden by subclasses which do implement directory support.
        """
        return False

    def create_subordinate_passes(self) -> list[AbstractPass]:
        """Additional passes that perform the work needed for this pass.

        By default empty; useful for implementing parallelization of pass initialization.
        """
        return []

    def new(
        self, test_case: Path, tmp_dir: Path, job_timeout: int, process_event_notifier: ProcessEventNotifier, **kwargs
    ) -> Any:
        raise NotImplementedError(f"Class {type(self).__name__} has not implemented 'new'!")

    def advance(self, test_case: Path, state) -> Any:
        raise NotImplementedError(f"Class {type(self).__name__} has not implemented 'advance'!")

    def advance_on_success(
        self,
        test_case: Path,
        state,
        new_tmp_dir: Path,
        succeeded_state,
        job_timeout,
        process_event_notifier: ProcessEventNotifier,
        **kwargs,
    ) -> Any:
        raise NotImplementedError(f"Class {type(self).__name__} has not implemented 'advance_on_success'!")

    def transform(
        self, test_case: Path, state, process_event_notifier: ProcessEventNotifier, original_test_case: Path, **kwargs
    ) -> tuple[PassResult, Any]:
        raise NotImplementedError(f"Class {type(self).__name__} has not implemented 'transform'!")

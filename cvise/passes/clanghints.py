from __future__ import annotations

import logging
import shlex
import subprocess
import time
from pathlib import Path

import msgspec

from cvise.passes.abstract import BinaryState, SubsegmentState
from cvise.passes.hint_based import HintBasedPass, HintState
from cvise.utils.hint import Hint, HintBundle
from cvise.utils.process import ProcessEventNotifier

CLANG_STD_CHOICES = ('c++98', 'c++11', 'c++14', 'c++17', 'c++20', 'c++2b')


class ClangState(HintState):
    """Extends HintState to store additional information needed by ClangHintsPass.

    See the comment in ClangHintsPass for the background."""

    clang_std: str | None

    @staticmethod
    def wrap(parent: HintState | None, clang_std: str | None) -> HintState | None:
        if parent is None:
            return None
        wrapped = object.__new__(ClangState)
        wrapped.__dict__.update(parent.__dict__)
        wrapped.clang_std = clang_std
        return wrapped


class ClangDeltaError(Exception):
    pass


class ClangHintsPass(HintBasedPass):
    """A pass that performs reduction using the hints produced by the clang_delta tool.

    Implementation-wise, we don't use default new/advance/advance_on_success implementation from the base class, because
    we want to brute-force Clang's `--std=` parameter that maximizes the generated set of hints (unless "iterate_stds"
    is False). This requires having special logic in new() and carrying over some extra information from new() to
    advance_on_success() throughout all advance() calls.

    Strategy by default is "binsearch" - trying all instances first, then the first half, then the second, etc. Another
    supported strategy is "onebyone" - attempting each instance, starting from a random one, individually.
    """

    def __init__(
        self,
        arg: str,
        external_programs: dict[str, str | None],
        user_clang_delta_std: str | None = None,
        strategy: str | None = None,
        iterate_stds: bool | None = None,
        **kwargs,
    ):
        super().__init__(
            arg=arg, external_programs=external_programs, user_clang_delta_std=user_clang_delta_std, **kwargs
        )
        self._user_clang_delta_std = user_clang_delta_std
        self._strategy = strategy
        self._iterate_stds = iterate_stds == True

    def check_prerequisites(self):
        return self.check_external_program('clang_delta')

    def new(
        self, test_case: Path, tmp_dir: Path, job_timeout, process_event_notifier: ProcessEventNotifier, *args, **kwargs
    ):
        # If configured accordingly, choose the best standard unless the user provided one.
        if self._user_clang_delta_std:
            std_choices = [self._user_clang_delta_std]
        elif self._iterate_stds:
            std_choices = CLANG_STD_CHOICES
        else:
            std_choices = [None]  # denotes not specifying "--std=" at all

        best_std = None
        best_bundle: HintBundle | None = None
        last_error: ClangDeltaError | None = None
        for std in std_choices:
            start = time.monotonic()
            try:
                bundle = self._generate_hints_for_standard(test_case, std, job_timeout, process_event_notifier)
            except ClangDeltaError as e:
                last_error = e
                continue
            took = time.monotonic() - start
            # prefer newer standard if the # of instances is equal
            if best_bundle is None or len(bundle.hints) >= len(best_bundle.hints):
                best_std = std
                best_bundle = bundle
            logging.debug(
                'available transformation opportunities for %s: %d, took: %.2f s' % (std, len(bundle.hints), took)
            )

        if best_bundle is None:
            logging.warning('%s', last_error)
            return None

        if best_std:
            logging.info(
                'clang_delta %s using C++ standard: %s with %d transformation opportunities',
                self.arg,
                best_std,
                len(best_bundle.hints),
            )
        else:
            logging.debug(
                'clang_delta %s: %d transformation opportunities',
                self.arg,
                len(best_bundle.hints),
            )
        # Let the parent class complete the initialization, but create our own state to remember the chosen standard.
        hint_state = self.new_from_hints(best_bundle, tmp_dir)
        return ClangState.wrap(hint_state, best_std)

    def advance(self, test_case: Path, state):
        new_state = super().advance(test_case, state)
        # Re-attach the remembered standard.
        return ClangState.wrap(new_state, state.clang_std)

    def advance_on_success(
        self,
        test_case: Path,
        state,
        new_tmp_dir: Path,
        job_timeout: int,
        process_event_notifier: ProcessEventNotifier,
        *args,
        **kwargs,
    ):
        # Keep using the same standard as the one chosen in new() - repeating the choose procedure on every successful
        # reduction would be too costly.
        try:
            hints = self._generate_hints_for_standard(test_case, state.clang_std, job_timeout, process_event_notifier)
        except ClangDeltaError as e:
            logging.warning('%s', e)
            return None
        new_state = self.advance_on_success_from_hints(hints, state, new_tmp_dir)
        return ClangState.wrap(new_state, state.clang_std)

    def create_elementary_state(self, hint_count: int) -> BinaryState | SubsegmentState | None:
        if self._strategy == 'binsearch' or self._strategy is None:  # default strategy
            return BinaryState.create(instances=hint_count)
        if self._strategy == 'onebyone':
            return SubsegmentState.create(instances=hint_count, min_chunk=1, max_chunk=1)
        raise ValueError(f'Unexpected strategy: {self._strategy}')

    def _generate_hints_for_standard(
        self, test_case: Path, std: str | None, timeout: int, process_event_notifier: ProcessEventNotifier
    ) -> HintBundle:
        options = [f'--transformation={self.arg}', '--generate-hints']
        if std is not None:
            options.append(f'--std={std}')

        cmd = [self.external_programs['clang_delta']] + options + [str(test_case)]
        logging.debug(shlex.join(str(s) for s in cmd))

        try:
            stdout, stderr, returncode = process_event_notifier.run_process(cmd, timeout=timeout)
        except subprocess.TimeoutExpired as e:
            raise ClangDeltaError(f'clang_delta ({" ".join(options)}) {timeout}s timeout reached') from e
        except subprocess.SubprocessError as e:
            raise ClangDeltaError(f'clang_delta ({" ".join(options)}) failed: {e}') from e

        if returncode != 0:
            stderr = stderr.decode('utf-8', 'ignore').strip()
            delim = ': ' if stderr else ''
            raise ClangDeltaError(
                f'clang_delta ({" ".join(options)}) failed with exit code {returncode}{delim}{stderr}'
            )
        return parse_clang_delta_hints(stdout)


def parse_clang_delta_hints(stdout: bytes) -> HintBundle:
    # When reading, gracefully handle EOF because the tool might've failed with no output.
    if not stdout.strip():
        return HintBundle(hints=[])
    stdout_view = memoryview(stdout)

    # Read vocabulary: size, newline, zero-separated string list.
    pos = stdout.index(b'\n')
    vocab_size = int(stdout_view[:pos])
    pos += 1
    vocab = []
    for _ in range(vocab_size):
        end = stdout.index(0, pos)
        vocab.append(bytes(stdout_view[pos:end]))
        pos = end + 1

    # Read hints.
    hints = []
    hint_decoder = msgspec.json.Decoder(type=Hint)
    while pos < len(stdout):
        end = stdout.index(b'\n', pos)
        hints.append(hint_decoder.decode(stdout_view[pos:end]))
        pos = end + 1

    return HintBundle(vocabulary=vocab, hints=hints)

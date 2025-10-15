import logging
import shlex
import subprocess
import time
from pathlib import Path
from typing import Optional, Union

import msgspec

from cvise.passes.hint_based import HintBasedPass, HintState
from cvise.utils.hint import Hint, HintBundle
from cvise.utils.process import ProcessEventNotifier

CLANG_STD_CHOICES = ('c++98', 'c++11', 'c++14', 'c++17', 'c++20', 'c++2b')


class ClangState(HintState):
    """Extends HintState to store additional information needed by ClangHintsPass.

    See the comment in ClangHintsPass for the background."""

    clang_std: str

    @staticmethod
    def wrap(parent: Union[HintState, None], clang_std: str) -> Union[HintState, None]:
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
    we want to brute-force Clang's `--std=` parameter that maximizes the generated set of hints. This requires having
    special logic in new() and carrying over some extra information from new() to advance_on_success() throughout all
    advance() calls.
    """

    def __init__(
        self,
        arg: str,
        external_programs: dict[str, Optional[str]],
        user_clang_delta_std: Optional[str] = None,
        **kwargs,
    ):
        super().__init__(
            arg=arg, external_programs=external_programs, user_clang_delta_std=user_clang_delta_std, **kwargs
        )
        self._user_clang_delta_std = user_clang_delta_std

    def check_prerequisites(self):
        return self.check_external_program('clang_delta')

    def new(
        self, test_case: Path, tmp_dir: Path, job_timeout, process_event_notifier: ProcessEventNotifier, *args, **kwargs
    ):
        # Choose the best standard unless the user provided one.
        std_choices = [self._user_clang_delta_std] if self._user_clang_delta_std else CLANG_STD_CHOICES
        best_std = None
        best_bundle: Union[HintBundle, None] = None
        last_error: Union[ClangDeltaError, None] = None
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
        assert best_std is not None

        logging.info(
            'clang_delta %s using C++ standard: %s with %d transformation opportunities',
            self.arg,
            best_std,
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

    def _generate_hints_for_standard(
        self, test_case: Path, std: str, timeout: int, process_event_notifier: ProcessEventNotifier
    ) -> HintBundle:
        cmd = [
            self.external_programs['clang_delta'],
            f'--transformation={self.arg}',
            f'--std={std}',
            '--generate-hints',
            str(test_case),
        ]

        logging.debug(shlex.join(str(s) for s in cmd))

        try:
            stdout, stderr, returncode = process_event_notifier.run_process(cmd, timeout=timeout)
        except subprocess.TimeoutExpired as e:
            raise ClangDeltaError(
                f'clang_delta (--transformation={self.arg} --std={std}) {timeout}s timeout reached'
            ) from e
        except subprocess.SubprocessError as e:
            raise ClangDeltaError(f'clang_delta (--transformation={self.arg} --std={std}) failed: {e}') from e

        if returncode != 0:
            stderr = stderr.decode('utf-8', 'ignore').strip()
            delim = ': ' if stderr else ''
            raise ClangDeltaError(
                f'clang_delta (--transformation={self.arg} --std={std}) failed with exit code {returncode}{delim}{stderr}'
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

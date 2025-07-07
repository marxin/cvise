import json
import logging
from pathlib import Path
import shlex
import subprocess
import time
from typing import Union

from cvise.passes.abstract import BinaryState
from cvise.passes.hint_based import HintBasedPass, HintState
from cvise.utils.hint import HintBundle


CLANG_STD_CHOICES = ('c++98', 'c++11', 'c++14', 'c++17', 'c++20', 'c++2b')


class ClangState(HintState):
    """Extends HintState to store additional information needed by ClangHintsPass.

    See the comment in ClangHintsPass for the background."""

    def __init__(self, clang_std: str, hint_count: int, hints_file_path: Path, binary_state: BinaryState):
        super().__init__(hint_count, hints_file_path, binary_state)
        self.clang_std = clang_std

    @staticmethod
    def wrap(parent: Union[HintState, None], clang_std: str) -> Union[HintState, None]:
        if parent is None:
            return None
        return ClangState(clang_std, parent.hint_count, parent.hints_file_path, parent.binary_state)


class ClangHintsPass(HintBasedPass):
    """A pass that performs reduction using the hints produced by the clang_delta tool.

    Implementation-wise, we don't use default new/advance/advance_on_success implementation from the base class, because
    we want to brute-force Clang's `--std=` parameter that maximizes the generated set of hints. This requires having
    special logic in new() and carrying over some extra information from new() to advance_on_success() throughout all
    advance() calls.
    """

    def check_prerequisites(self):
        return self.check_external_program('clang_delta')

    def new(self, test_case, tmp_dir, **kwargs):
        # Choose the best standard unless the user provided one.
        std_choices = [self.user_clang_delta_std] if self.user_clang_delta_std else CLANG_STD_CHOICES
        best_std = None
        best_bundle = None
        for std in std_choices:
            start = time.monotonic()
            bundle = self.generate_hints_for_standard(test_case, std)
            took = time.monotonic() - start
            # prefer newer standard if the # of instances is equal
            if best_bundle is None or len(bundle.hints) >= len(best_bundle.hints):
                best_std = std
                best_bundle = bundle
            logging.debug(
                'available transformation opportunities for %s: %d, took: %.2f s' % (std, len(bundle.hints), took)
            )
        logging.info('using C++ standard: %s with %d transformation opportunities' % (best_std, len(best_bundle.hints)))

        # Let the parent class complete the initialization, but create our own state to remember the chosen standard.
        hint_state = self.new_from_hints(best_bundle, tmp_dir)
        return ClangState.wrap(hint_state, best_std)

    def advance(self, test_case, state):
        new_state = super().advance(test_case, state)
        # Re-attach the remembered standard.
        return ClangState.wrap(new_state, state.clang_std)

    def advance_on_success(self, test_case, state):
        # Keep using the same standard as the one chosen in new() - repeating the choose procedure on every successful
        # reduction would be too costly.
        hints = self.generate_hints_for_standard(test_case, state.clang_std)
        new_state = self.advance_on_success_from_hints(hints, state)
        return ClangState.wrap(new_state, state.clang_std)

    def generate_hints_for_standard(self, test_case, std) -> HintBundle:
        cmd = [
            self.external_programs['clang_delta'],
            f'--transformation={self.arg}',
            f'--std={std}',
            '--generate-hints',
            test_case,
        ]

        logging.debug(shlex.join(str(s) for s in cmd))

        hints = []
        # FIXME: Set a timeout.
        with subprocess.Popen(cmd, stdout=subprocess.PIPE, text=True) as proc:
            vocab = json.loads(next(proc.stdout))
            for line in proc.stdout:
                if not line.isspace():
                    hints.append(json.loads(line))
        return HintBundle(vocabulary=vocab, hints=hints)

import msgspec
from pathlib import Path
from typing import Dict, List, Union

from cvise.passes.hint_based import HintBasedPass
from cvise.utils.hint import Hint, HintBundle, Patch
from cvise.utils.process import ProcessEventNotifier


class LinesPass(HintBasedPass):
    def check_prerequisites(self):
        return self.check_external_program('topformflat_hints')

    def supports_dir_test_cases(self):
        return True

    def generate_hints(self, test_case: Path, process_event_notifier: ProcessEventNotifier, *args, **kwargs):
        vocab = []
        hints = []
        decoder = msgspec.json.Decoder(type=Hint)
        if test_case.is_dir():
            for path in test_case.rglob('*'):
                if not path.is_dir():
                    vocab.append(str(path.relative_to(test_case)))
                    file_id = len(vocab) - 1
                    hints += self._generate_hints_for_file(path, decoder, process_event_notifier, file_id)
        else:
            hints += self._generate_hints_for_file(test_case, decoder, process_event_notifier, file_id=None)
        return HintBundle(hints=hints, vocabulary=vocab)

    def _generate_hints_for_file(
        self,
        file_path: Path,
        decoder: msgspec.json.Decoder,
        process_event_notifier: ProcessEventNotifier,
        file_id: Union[int, None],
    ) -> List[Dict]:
        if self.arg == 'None':
            # None means no topformflat
            return self._generate_hints_for_text_lines(file_path, file_id)
        else:
            return self._generate_topformflat_hints(file_path, decoder, process_event_notifier, file_id)

    def _generate_hints_for_text_lines(self, test_case: Path, file_id: Union[int, None]) -> List[Dict]:
        """Generate a hint per each line in the input as written."""
        hints = []
        with open(test_case, 'rb') as in_file:
            file_pos = 0
            for line in in_file:
                end_pos = file_pos + len(line)
                patch = Patch(l=file_pos, r=end_pos)
                if file_id is not None:
                    patch.f = file_id
                hints.append(Hint(p=[patch]))
                file_pos = end_pos
        return hints

    def _generate_topformflat_hints(
        self,
        test_case: Path,
        decoder: msgspec.json.Decoder,
        process_event_notifier: ProcessEventNotifier,
        file_id: Union[int, None],
    ) -> List[Dict]:
        """Generate hints via the modified topformflat tool.

        A single hint here is, roughly, a curly brace surrounded block at the
        nesting level specified by the arg integer.
        """
        cmd = [self.external_programs['topformflat_hints'], self.arg]
        with open(test_case, 'rb') as in_file:
            stdout = process_event_notifier.check_output(cmd, stdin=in_file)

        hints = []
        for line in stdout.splitlines():
            if not line.isspace():
                hint = decoder.decode(line)
                assert len(hint.p) == 1
                if file_id is not None:
                    hint.p[0].f = file_id
                hints.append(hint)
        return hints

import msgspec
from pathlib import Path
import subprocess
from typing import Optional

from cvise.passes.hint_based import HintBasedPass
from cvise.utils.fileutil import filter_files_by_patterns
from cvise.utils.hint import Hint, HintBundle, Patch
from cvise.utils.process import ProcessEventNotifier


class LinesPass(HintBasedPass):
    def __init__(self, arg: str, external_programs: dict[str, Optional[str]], **kwargs):
        super().__init__(arg=arg, external_programs=external_programs, **kwargs)

    def check_prerequisites(self):
        return self.check_external_program('topformflat_hints')

    def supports_dir_test_cases(self):
        return True

    def generate_hints(self, test_case: Path, process_event_notifier: ProcessEventNotifier, *args, **kwargs):
        is_dir = test_case.is_dir()
        paths = filter_files_by_patterns(test_case, self.claim_files, self.claimed_by_others_files)
        vocab = [str(p.relative_to(test_case)).encode() for p in paths] if is_dir else []
        hints = []
        for i, path in enumerate(paths):
            file_id = i if is_dir else None
            if self.arg == 'None':
                self._generate_hints_for_text_lines(path, file_id, hints)
            else:
                self._generate_topformflat_hints(test_case, is_dir, paths, process_event_notifier, hints)

        return HintBundle(hints=hints, vocabulary=vocab)

    def _generate_hints_for_text_lines(self, input_path: Path, file_id: Optional[int], hints: list[Hint]) -> None:
        """Generate a hint per each line in the input as written."""
        with open(input_path, 'rb') as in_file:
            file_pos = 0
            for line in in_file:
                end_pos = file_pos + len(line)
                hints.append(Hint(patches=(Patch(left=file_pos, right=end_pos, file=file_id),)))
                file_pos = end_pos

    def _generate_topformflat_hints(
        self,
        test_case: Path,
        is_dir: bool,
        paths: list[Path],
        process_event_notifier: ProcessEventNotifier,
        hints: list[Hint],
    ) -> None:
        """Generate hints via the modified topformflat tool.

        A single hint here is, roughly, a curly brace surrounded block at the
        nesting level specified by the arg integer.
        """
        # If the test case is a single file, simply specify its path via cmd line. If it's a directory, enumerate all
        # files (we do it on the Python side for flexibility) and send the list via stdin (to not hit the cmd line size
        # limit).
        if is_dir:
            work_dir = test_case
            stdin = b'\0'.join(bytes(p.relative_to(test_case)) for p in paths)
            cmd_file_arg = '--'
        else:
            work_dir = None
            stdin = b''
            cmd_file_arg = str(test_case)

        cmd = [self.external_programs['topformflat_hints'], self.arg, cmd_file_arg]
        stdout = process_event_notifier.check_output(cmd, cwd=work_dir, stdin=subprocess.PIPE, input=stdin)

        decoder = msgspec.json.Decoder(type=Hint)
        for line in stdout.splitlines():
            if not line.isspace():
                hint = decoder.decode(line)
                assert len(hint.patches) == 1
                hints.append(hint)

import json
import subprocess
from typing import Sequence

from cvise.passes.hint_based import HintBasedPass
from cvise.utils.hint import HintBundle


class LinesPass(HintBasedPass):
    def check_prerequisites(self):
        return self.check_external_program('topformflat_hints')

    def generate_hints(self, test_case):
        if self.arg == 'None':
            # None means no topformflat
            return self.generate_hints_for_text_lines(test_case)
        else:
            return self.generate_topformflat_hints(test_case)

    def generate_hints_for_text_lines(self, test_case: str) -> HintBundle:
        """Generate a hint per each line in the input as written."""
        hints = []
        with open(test_case) as in_file:
            file_pos = 0
            for line in in_file:
                end_pos = file_pos + len(line)
                hints.append({'p': [{'l': file_pos, 'r': end_pos}]})
            file_pos = end_pos
        return HintBundle(hints=hints)

    def generate_topformflat_hints(self, test_case: str) -> HintBundle:
        """Generate hints via the modified topformflat tool.

        A single hint here is, roughly, a curly brace surrounded block at the
        nesting level specified by the arg integer."""
        hints = []
        cmd = [self.external_programs['topformflat_hints'], self.arg]
        with open(test_case) as in_file:
            with subprocess.Popen(cmd, stdin=in_file, stdout=subprocess.PIPE, text=True) as proc:
                for line in proc.stdout:
                    if not line.isspace():
                        hints.append(json.loads(line))
        return HintBundle(hints=hints)

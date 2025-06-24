import re

from cvise.passes.hint_based import HintBasedPass


class LineMarkersPass(HintBasedPass):
    line_regex = re.compile('^\\s*#\\s*[0-9]+')

    def check_prerequisites(self):
        return True

    def generate_hints(self, test_case):
        hints = []
        with open(test_case) as in_file:
            file_pos = 0
            for line in in_file.readlines():
                end_pos = file_pos + len(line)
                if self.line_regex.search(line):
                    hints.append({'p': [{'l': file_pos, 'r': end_pos}]})
                file_pos = end_pos
        return hints

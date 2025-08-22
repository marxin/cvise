from pathlib import Path
import re

from cvise.passes.hint_based import HintBasedPass
from cvise.utils.hint import HintBundle


class LineMarkersPass(HintBasedPass):
    """A pass that removes C/C++ preprocessor line markers.

    Quoting the GCC documentation on the preprocessor output:

    > Source file name and line number information is conveyed by lines of the form
    > # linenum filename flags
    > These are called linemarkers. They are inserted as needed into the output (but never within a string or character
    > constant).

    Since minimization inputs are typically preprocessed C/C++ programs, there are line markers in them. They bloat
    the input size while not usually (*) being essential for the interestingness test, hence this special pass
    attempts recognizing and deleting them.

    (*) Sometimes the line markers are crucial (e.g., for compiler logic that depends on whether code lives in a
    system header) and cannot be removed. Also the pass implementation, being a simple regexp, can have false positives.
    """

    line_regex = re.compile(b'^\\s*#\\s*[0-9]+')

    def check_prerequisites(self):
        return True

    def generate_hints(self, test_case: Path, *args, **kwargs):
        hints = []
        with open(test_case, 'rb') as in_file:
            file_pos = 0
            for line in in_file.readlines():
                end_pos = file_pos + len(line)
                if self.line_regex.search(line):
                    hints.append({'p': [{'l': file_pos, 'r': end_pos}]})
                file_pos = end_pos
        return HintBundle(hints=hints)

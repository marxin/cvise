import os
from pathlib import Path
from typing import Set


class CViseError(Exception):
    pass


class PrerequisitesNotFoundError(CViseError):
    def __init__(self, missing):
        self.missing = missing

    def __str__(self):
        return 'Missing prerequisites for passes {}!'.format(', '.join(self.missing))


class UnknownArgumentError(CViseError):
    def __init__(self, pass_, arg):
        self.pass_ = pass_
        self.arg = arg

    def __str__(self):
        return f"The argument '{self.arg}' is not valid for pass '{self.pass_.__name__}'!"


class InvalidFileError(CViseError):
    def __init__(self, path: Path, error):
        self.path = path
        self.error = error

    def _get_error_name(self):
        if self.error == os.R_OK:
            return 'read'
        elif self.error == os.W_OK:
            return 'written'
        elif self.error == os.X_OK:
            return 'executed'
        elif self.error == os.F_OK:
            return 'accessed'

    def __str__(self):
        return f"The specified file '{self.path}' cannot be {self._get_error_name()}!"


class InvalidTestCaseError(InvalidFileError):
    def __str__(self):
        return f"The specified test case '{self.path}' cannot be {self._get_error_name()}!"


class AbsolutePathTestCaseError(CViseError):
    def __init__(self, path: Path):
        self.path = path

    def __str__(self):
        return f"Test case path cannot be absolute: '{self.path}'!"


class InvalidInterestingnessTestError(InvalidFileError):
    def __init__(self, path: Path):
        super().__init__(path, None)

    def __str__(self):
        return f"The specified interestingness test '{self.path}' cannot be executed!"


class ZeroSizeError(CViseError):
    def __init__(self, test_cases: Set[Path]):
        super().__init__()
        self.test_cases = test_cases

    def __str__(self):
        if len(self.test_cases) == 1:
            message = 'The file being reduced has reached zero size; '
        else:
            message = 'All files being reduced have reached zero size; '

        message += """our work here is done.

If you did not want a zero size file, you must help C-Vise out by
making sure that your interestingness test does not find files like
this to be interesting."""
        return message


class PassOptionError(CViseError):
    pass


class MissingPassGroupsError(CViseError):
    def __str__(self):
        return 'Could not find a directory with definitions for pass groups!'


class PassBugError(CViseError):
    MSG = """***************************************************

{} has encountered a bug:
{}
state: {}

Please consider tarring up {}
and creating an issue at https://github.com/marxin/cvise/issues and we will try to fix the bug.

***************************************************
"""

    def __init__(self, current_pass, problem, state, crash_dir: Path):
        super().__init__()
        self.current_pass = current_pass
        self.state = state
        self.problem = problem
        self.crash_dir = crash_dir

    def __str__(self):
        return self.MSG.format(self.current_pass, self.problem, self.state, self.crash_dir)


class InsaneTestCaseError(CViseError):
    def __init__(self, test_cases: Set[Path], test: Path):
        super().__init__()
        self.test_cases = test_cases
        self.test = test

    def __str__(self):
        message = """C-Vise cannot run because the interestingness test does not return
zero. Please ensure that it does so not only in the directory where
you are invoking C-Vise, but also in an arbitrary temporary
directory containing only the files that are being reduced. In other
words, running these commands:

  DIR=`mktemp -d`
  cp {test_cases} $DIR
  cd $DIR
  {test}
  echo $?

should result in '0' being echoed to the terminal.
Please ensure that the test script takes no arguments; it should be hard-coded to refer
to the same file that is passed as an argument to C-Vise.

See 'cvise-cli.py --help' for more information.""".format(
            test_cases=' '.join([str(t) for t in self.test_cases]), test=self.test
        )
        return message

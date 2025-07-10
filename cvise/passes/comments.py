import re

from cvise.passes.abstract import AbstractPass, PassResult


class CommentsPass(AbstractPass):
    def check_prerequisites(self):
        return True

    def new(self, test_case, **kwargs):
        return -2

    def advance(self, test_case, state):
        return state + 1

    def advance_on_success(self, test_case, state, **kwargs):
        return state

    def transform(self, test_case, state, process_event_notifier):
        with open(test_case) as in_file:
            prog = in_file.read()
            prog2 = prog

        while True:
            # TODO: remove only the nth comment
            if state == -2:
                # Remove all multiline comments
                # Replace /* any number of * if not followed by / or anything but * */
                prog2 = re.sub(r'/\*(?:\*(?!/)|[^*])*\*/', '', prog2, flags=re.DOTALL)
            elif state == -1:
                # Remove all single line comments
                prog2 = re.sub(r'//.*$', '', prog2, flags=re.MULTILINE)
            else:
                return (PassResult.STOP, state)

            if prog != prog2:
                with open(test_case, 'w') as out_file:
                    out_file.write(prog2)

                return (PassResult.OK, state)
            else:
                state = self.advance(test_case, state)

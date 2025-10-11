from pathlib import Path
import tempfile
from typing import Any
import unittest

from cvise.passes.abstract import ProcessEventNotifier
from cvise.passes.ifs import IfPass


class LineMarkersTestCase(unittest.TestCase):
    def setUp(self):
        # TODO: use enterContext() once Python 3.11 is the oldest supported release
        self.tmp_dir_obj = tempfile.TemporaryDirectory()
        self.tmp_dir: Path = Path(self.tmp_dir_obj.name)
        self.input_path: Path = self.tmp_dir / 'test_case'
        self.pass_ = IfPass(external_programs={'unifdef': 'unifdef'})
        self.process_event_notifier = ProcessEventNotifier(None)

    def tearDown(self):
        self.tmp_dir_obj.cleanup()

    def test_all(self):
        self.input_path.write_text('#if FOO\nint a = 2;\n#endif')

        state = self.pass_.new(self.input_path)
        state = self.pass_.advance(self.input_path, state)
        (_, state) = self.pass_.transform(self.input_path, state, self.process_event_notifier)
        self.assertEqual(state.index, 0)
        self.assertEqual(state.instances, 1)

        variant = self.input_path.read_text()

        self.assertEqual(variant, 'int a = 2;\n')

    def test_two_steps(self):
        self.maxDiff = None
        in_contents = (
            '#if FOO\nint foo = 1;\n#else\nint foo = 0;\n#endif\n'
            + '#if BAR\nint bar = 1;\n#else\nint bar = 0;\n#endif\n'
        )
        expected_outs = [
            # ix val chunk contents
            # FOO=0 BAR=0
            (0, 0, 2, 'int foo = 0;\nint bar = 0;\n'),
            # FOO=1 BAR=1
            (0, 1, 2, 'int foo = 1;\nint bar = 1;\n'),
            # FOO=0
            (
                0,
                0,
                1,
                ('int foo = 0;\n' + '#if BAR\nint bar = 1;\n#else\nint bar = 0;\n#endif\n'),
            ),
            # FOO=1
            (
                0,
                1,
                1,
                ('int foo = 1;\n' + '#if BAR\nint bar = 1;\n#else\nint bar = 0;\n#endif\n'),
            ),
            # BAR=0
            (
                1,
                0,
                1,
                ('#if FOO\nint foo = 1;\n#else\nint foo = 0;\n#endif\n' + 'int bar = 0;\n'),
            ),
            # BAR=1
            (
                1,
                1,
                1,
                ('#if FOO\nint foo = 1;\n#else\nint foo = 0;\n#endif\n' + 'int bar = 1;\n'),
            ),
        ]

        self.input_path.write_text(in_contents)

        outs = []

        # perform all iterations. They should iterate through FOO/!FOO x BAR/!BAR.
        state = self.pass_.new(self.input_path)
        while state:
            self.input_path.write_text(in_contents)

            (_, state) = self.pass_.transform(self.input_path, state, self.process_event_notifier)
            variant = self.input_path.read_text()
            state: Any  # workaround type-checkers not seeing the "value" attribute
            outs.append((state.index, state.value, state.chunk, variant))
            state = self.pass_.advance(self.input_path, state)

        self.assertEqual(expected_outs, outs)

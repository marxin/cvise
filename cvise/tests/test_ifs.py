import os
from pathlib import Path
import tempfile
from typing import Any
import unittest

from cvise.passes.abstract import ProcessEventNotifier
from cvise.passes.ifs import IfPass


class LineMarkersTestCase(unittest.TestCase):
    def setUp(self):
        self.pass_ = IfPass(external_programs={'unifdef': 'unifdef'})
        self.process_event_notifier = ProcessEventNotifier(None)

    def test_all(self):
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as tmp_file:
            tmp_file.write('#if FOO\nint a = 2;\n#endif')
            tmp_path = Path(tmp_file.name)

        state = self.pass_.new(tmp_path)
        state = self.pass_.advance(tmp_path, state)
        (_, state) = self.pass_.transform(tmp_path, state, self.process_event_notifier)
        self.assertEqual(state.index, 0)
        self.assertEqual(state.instances, 1)

        variant = tmp_path.read_text()

        tmp_path.unlink()
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

        with tempfile.NamedTemporaryFile(mode='w', delete=False) as tf:
            tf.write(in_contents)
            tf_path = Path(tf.name)

        outs = []

        # perform all iterations. They should iterate through FOO/!FOO x BAR/!BAR.
        state = self.pass_.new(tf_path)
        while state:
            with tempfile.NamedTemporaryFile(mode='w', delete=False) as tmp_file:
                tmp_file.write(in_contents)
                tmp_path = Path(tmp_file.name)

            (_, state) = self.pass_.transform(tmp_path, state, self.process_event_notifier)
            variant = tmp_path.read_text()
            state: Any  # workaround type-checkers not seeing the "value" attribute
            outs.append((state.index, state.value, state.chunk, variant))
            tmp_path.unlink()
            state = self.pass_.advance(tmp_path, state)

        tf_path.unlink()
        self.assertEqual(expected_outs, outs)

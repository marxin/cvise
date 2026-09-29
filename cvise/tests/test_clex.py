import shutil
from pathlib import Path
from typing import Any

import pytest

from cvise.passes.abstract import PassResult
from cvise.passes.clex import ClexPass
from cvise.utils.externalprograms import find_external_programs
from cvise.utils.process import ProcessEventNotifier
from cvise.utils import sigmonitor


@pytest.fixture(autouse=True)
def signal_monitor():
    sigmonitor.init()


@pytest.fixture
def input_path(tmp_path: Path) -> Path:
    return tmp_path / 'input.cc'


def init_clex_pass(arg: str, input_path: Path) -> tuple[ClexPass, Any]:
    pass_ = ClexPass(arg, find_external_programs())
    state = pass_.new(input_path)
    return pass_, state


def test_clex_pattern_nested_brackets(tmp_path: Path, input_path: Path):
    """Test the scenario of "flattening" a generic; it's crucial that >> is treated as two tokens."""
    input_path.write_text('Foo<Bar<Baz>>')
    pass_, state = init_clex_pass('rm-tok-pattern-4', input_path)
    all_transforms = set()

    while state is not None:
        test_case = tmp_path / 'test.cc'
        shutil.copy(input_path, test_case)
        result, _new_state = pass_.transform(test_case, state, process_event_notifier=ProcessEventNotifier(None))
        if result == PassResult.OK:
            all_transforms.add(test_case.read_bytes())
        elif result == PassResult.STOP:
            break
        state = pass_.advance(input_path, state)

    assert b'Foo<Baz>' in all_transforms

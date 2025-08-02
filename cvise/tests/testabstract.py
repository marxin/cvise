import jsonschema
from pathlib import Path
from typing import Collection, Union

from cvise.passes.abstract import AbstractPass, PassResult, ProcessEventNotifier
from cvise.passes.hint_based import HintState
from cvise.utils.hint import HINT_SCHEMA_STRICT, HintBundle, load_hints


def iterate_pass(current_pass, path, **kwargs):
    state = current_pass.new(path, **kwargs)
    while state is not None:
        (result, state) = current_pass.transform(path, state, ProcessEventNotifier(None))
        if result == PassResult.OK:
            state = current_pass.advance_on_success(path, state)
        else:
            state = current_pass.advance(path, state)


def collect_all_transforms(pass_: AbstractPass, state, input_path: Path) -> Collection[bytes]:
    all_outputs = set()
    backup = input_path.read_bytes()
    while state is not None:
        pass_.transform(input_path, state, process_event_notifier=None)
        all_outputs.add(input_path.read_bytes())
        input_path.write_bytes(backup)
        state = pass_.advance(input_path, state)
    return all_outputs


def validate_stored_hints(state: Union[HintState, None]) -> None:
    if state is None:
        return
    for substate in state.per_type_states:
        path = state.tmp_dir / substate.hints_file_name
        bundle = load_hints(path, 0, substate.underlying_state.instances)
        validate_hint_bundle(bundle)


def validate_hint_bundle(bundle: HintBundle) -> None:
    for hint in bundle.hints:
        jsonschema.validate(hint, HINT_SCHEMA_STRICT)
        # Also check the things that the JSON Schema cannot enforce.
        if 't' in hint:
            assert hint['t'] < len(bundle.vocabulary)
        for patch in hint['p']:
            assert patch['l'] < patch['r']
            if 'v' in patch:
                assert patch['v'] < len(bundle.vocabulary)

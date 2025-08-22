import jsonschema
from pathlib import Path
import tempfile
from typing import Set, Tuple, Union

from cvise.passes.abstract import AbstractPass, PassResult
from cvise.passes.hint_based import HintState
from cvise.utils.fileutil import CloseableTemporaryFile
from cvise.utils.hint import HINT_SCHEMA_STRICT, HintBundle, load_hints


def iterate_pass(current_pass: AbstractPass, path: Path, **kwargs) -> None:
    state = current_pass.new(path, **kwargs)
    while state is not None:
        (result, state) = current_pass.transform(path, state, process_event_notifier=None, original_test_case=path)
        if result == PassResult.OK:
            state = current_pass.advance_on_success(path, state)
        else:
            state = current_pass.advance(path, state)


def collect_all_transforms(pass_: AbstractPass, state, input_path: Path) -> Set[bytes]:
    all_outputs = set()
    with CloseableTemporaryFile() as tmp_file:
        tmp_path = Path(tmp_file.name)
        tmp_file.close()
        while state is not None:
            pass_.transform(tmp_path, state, process_event_notifier=None, original_test_case=input_path)
            all_outputs.add(tmp_path.read_bytes())
            state = pass_.advance(input_path, state)
    return all_outputs


def collect_all_transforms_dir(pass_: AbstractPass, state, input_path: Path) -> Set[Tuple[Tuple[str, bytes]]]:
    all_outputs = set()
    while state is not None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            pass_.transform(tmp_path, state, process_event_notifier=None, original_test_case=input_path)
            contents = tuple(
                sorted((str(p.relative_to(tmp_dir)), p.read_bytes()) for p in tmp_path.rglob('*') if not p.is_dir())
            )
            all_outputs.add(contents)
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

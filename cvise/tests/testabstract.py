import jsonschema
import msgspec
from pathlib import Path
import tempfile
from typing import Optional, Set, Tuple, Union

from cvise.passes.abstract import AbstractPass, PassResult
from cvise.passes.hint_based import HintBasedPass, HintState
from cvise.utils.fileutil import CloseableTemporaryFile
from cvise.utils.hint import HINT_SCHEMA_STRICT, HintBundle, load_hints
from cvise.utils.process import ProcessEventNotifier


def iterate_pass(current_pass: AbstractPass, path: Path, **kwargs) -> None:
    state = current_pass.new(path, **kwargs)
    while state is not None:
        (result, state) = current_pass.transform(
            path, state, process_event_notifier=ProcessEventNotifier(None), original_test_case=path
        )
        if result == PassResult.OK:
            state = current_pass.advance_on_success(
                path, state, process_event_notifier=ProcessEventNotifier(None), dependee_hints=[]
            )
        else:
            state = current_pass.advance(path, state)


def collect_all_transforms(pass_: AbstractPass, state, input_path: Path) -> Set[bytes]:
    all_outputs = set()
    with CloseableTemporaryFile() as tmp_file:
        tmp_path = Path(tmp_file.name)
        tmp_file.close()
        while state is not None:
            result, _new_state = pass_.transform(
                tmp_path, state, process_event_notifier=ProcessEventNotifier(None), original_test_case=input_path
            )
            if result == PassResult.OK:
                all_outputs.add(tmp_path.read_bytes())
                state = pass_.advance(input_path, state)
            elif result == PassResult.STOP:
                break
    return all_outputs


def collect_all_transforms_dir(pass_: AbstractPass, state, input_path: Path) -> Set[Tuple[Tuple[str, bytes]]]:
    all_outputs = set()
    while state is not None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            result, _new_state = pass_.transform(
                tmp_path, state, process_event_notifier=ProcessEventNotifier(None), original_test_case=input_path
            )
            if result == PassResult.OK:
                contents = tuple(
                    sorted((str(p.relative_to(tmp_dir)), p.read_bytes()) for p in tmp_path.rglob('*') if not p.is_dir())
                )
                all_outputs.add(contents)
                state = pass_.advance(input_path, state)
            elif result == PassResult.STOP:
                break
    return all_outputs


def validate_stored_hints(state: Union[HintState, None], pass_: HintBasedPass) -> None:
    if state is None:
        return
    output_types = set(pass_.output_hint_types())
    for substate in state.per_type_states:
        path = state.tmp_dir / substate.hints_file_name
        bundle = load_hints(path, 0, substate.underlying_state.instances)
        validate_hint_bundle(bundle, output_types)


def validate_hint_bundle(bundle: HintBundle, allowed_hint_types: Optional[Set[str]] = None) -> None:
    for hint in bundle.hints:
        # Check against JSON Schema.
        json_dump = msgspec.json.encode(hint)
        dict_obj = msgspec.json.decode(json_dump)
        jsonschema.validate(dict_obj, HINT_SCHEMA_STRICT)
        # Also check the things that the JSON Schema cannot enforce.
        if hint.t is not None:
            assert hint.t < len(bundle.vocabulary)
            hint_type = bundle.vocabulary[hint.t]
            if allowed_hint_types is not None:
                assert hint_type in allowed_hint_types
        for patch in hint.p:
            assert patch.l < patch.r
            if patch.v is not None:
                assert patch.v < len(bundle.vocabulary)

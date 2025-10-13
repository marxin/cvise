import jsonschema
import msgspec
from pathlib import Path
import tempfile
from typing import Optional, Union

from cvise.passes.abstract import AbstractPass, PassResult
from cvise.passes.hint_based import HintBasedPass, HintState
from cvise.utils.fileutil import CloseableTemporaryFile
from cvise.utils.hint import HINT_SCHEMA_STRICT, Hint, HintBundle, load_hints
from cvise.utils.process import ProcessEventNotifier


_TYPES_WITH_PATH_EXTRA = (b'@fileref',)
_KNOWN_OPERATIONS = (b'rm',)


def iterate_pass(current_pass: AbstractPass, path: Path, **kwargs) -> None:
    state = current_pass.new(path, **kwargs)
    while state is not None:
        (result, state) = current_pass.transform(
            path, state, process_event_notifier=ProcessEventNotifier(None), original_test_case=path, written_paths=set()
        )
        if result == PassResult.OK:
            state = current_pass.advance_on_success(
                path,
                state,
                new_tmp_dir=kwargs.get('tmp_dir', Path()),
                process_event_notifier=ProcessEventNotifier(None),
                dependee_hints=[],
                succeeded_state=None,
                job_timeout=0,
            )
        else:
            state = current_pass.advance(path, state)


def collect_all_transforms(pass_: AbstractPass, state, input_path: Path) -> set[bytes]:
    all_outputs = set()
    with CloseableTemporaryFile() as tmp_file:
        tmp_path = Path(tmp_file.name)
        tmp_file.close()
        while state is not None:
            result, _new_state = pass_.transform(
                tmp_path,
                state,
                process_event_notifier=ProcessEventNotifier(None),
                original_test_case=input_path,
                written_paths=set(),
            )
            if result == PassResult.OK:
                all_outputs.add(tmp_path.read_bytes())
                state = pass_.advance(input_path, state)
            elif result == PassResult.STOP:
                break
    return all_outputs


def collect_all_transforms_dir(pass_: AbstractPass, state, input_path: Path) -> set[tuple[tuple[str, bytes]]]:
    all_outputs = set()
    while state is not None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            result, _new_state = pass_.transform(
                tmp_path,
                state,
                process_event_notifier=ProcessEventNotifier(None),
                original_test_case=input_path,
                written_paths=set(),
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


def validate_stored_hints(state: Union[HintState, None], pass_: HintBasedPass, test_case: Path) -> None:
    if state is None:
        return
    output_types = set(pass_.output_hint_types())
    for substate in state.per_type_states:
        path = state.tmp_dir / substate.hints_file_name
        bundle = load_hints(path, 0, substate.underlying_state.instances)
        validate_hint_bundle(bundle, test_case, output_types)
    for substate in state.special_hints:
        path = state.tmp_dir / substate.hints_file_name
        bundle = load_hints(path, 0, substate.hint_count)
        validate_hint_bundle(bundle, test_case, output_types)


def validate_hint_bundle(bundle: HintBundle, test_case: Path, allowed_hint_types: Optional[set[bytes]] = None) -> None:
    for hint in bundle.hints:
        try:
            _validate_hint(hint, bundle, test_case, allowed_hint_types)
        except Exception as e:
            raise ValueError(f'Error validating hint {hint}') from e


def _validate_hint(hint: Hint, bundle: HintBundle, test_case: Path, allowed_hint_types: Optional[set[bytes]]) -> None:
    # Check against JSON Schema.
    json_dump = msgspec.json.encode(hint)
    dict_obj = msgspec.json.decode(json_dump)
    jsonschema.validate(dict_obj, HINT_SCHEMA_STRICT)
    # Also check the things that the JSON Schema cannot enforce.
    if hint.type is not None:
        assert hint.type < len(bundle.vocabulary)
        hint_type = bundle.vocabulary[hint.type]
        if allowed_hint_types is not None:
            assert hint_type in allowed_hint_types
    if hint.extra is not None:
        assert hint.extra < len(bundle.vocabulary)
        if hint.type is not None and bundle.vocabulary[hint.type] in _TYPES_WITH_PATH_EXTRA:
            path = Path(bundle.vocabulary[hint.extra].decode())
            assert not path.is_absolute()
            assert (test_case / path).exists()
            assert (test_case / path).is_relative_to(test_case)
    for patch in hint.patches:
        assert (patch.left is None) == (patch.right is None)
        assert (patch.path is not None) == test_case.is_dir()
        if patch.path is not None:
            assert patch.path < len(bundle.vocabulary)
            path = Path(bundle.vocabulary[patch.path].decode())
            assert not path.is_absolute()
            assert (test_case / path).exists()
            assert (test_case / path).is_relative_to(test_case)
            if patch.right is not None:
                assert patch.right <= (test_case / path).stat().st_size
        if patch.operation is not None:
            assert patch.operation < len(bundle.vocabulary)
            assert bundle.vocabulary[patch.operation] in _KNOWN_OPERATIONS
        else:
            # only special operations can use zero-size patches
            assert patch.left is not None
            assert patch.right is not None
            assert patch.left < patch.right
        if patch.value is not None:
            assert patch.value < len(bundle.vocabulary)

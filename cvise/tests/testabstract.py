from pathlib import Path

from cvise.passes.abstract import AbstractPass, PassResult, ProcessEventNotifier


def iterate_pass(current_pass, path, **kwargs):
    state = current_pass.new(path, **kwargs)
    while state is not None:
        (result, state) = current_pass.transform(path, state, ProcessEventNotifier(None))
        if result == PassResult.OK:
            state = current_pass.advance_on_success(path, state)
        else:
            state = current_pass.advance(path, state)


def collect_all_transforms(pass_: AbstractPass, state, input_path: Path):
    all_outputs = set()
    backup = input_path.read_text()
    while state is not None:
        pass_.transform(input_path, state, process_event_notifier=None)
        all_outputs.add(input_path.read_text())
        input_path.write_text(backup)
        state = pass_.advance(input_path, state)
    return all_outputs

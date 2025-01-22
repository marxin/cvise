import pytest

from cvise.passes.lines import LinesPass
from cvise.utils.externalprograms import find_external_programs


@pytest.fixture
def input_path(tmp_path):
    return tmp_path / 'input.cc'


@pytest.fixture
def external_programs():
    return find_external_programs()


def read_file(path):
    with open(path) as f:
        return f.read()


def write_file(path, data):
    with open(path, 'w') as f:
        f.write(data)


def collect_all_transforms(pass_, state, input_path):
    all_outputs = set()
    backup = read_file(input_path)
    while state is not None:
        pass_.transform(input_path, state, process_event_notifier=None)
        all_outputs.add(read_file(input_path))
        write_file(input_path, backup)
        state = pass_.advance(input_path, state)
    return all_outputs


def advance_until(pass_, state, input_path, predicate):
    backup = read_file(input_path)
    while True:
        pass_.transform(input_path, state, process_event_notifier=None)
        if predicate(read_file(input_path)):
            return state
        write_file(input_path, backup)
        state = pass_.advance(input_path, state)
        assert state is not None


def test_new_reformatting_arg0(input_path, external_programs):
    write_file(input_path, 'int f() {\nchar x;\n}\nnamespace foo\n{\n}\n')
    p = LinesPass('0', external_programs)
    p.new(input_path, check_sanity=lambda: True)
    assert read_file(input_path) == 'int f() { char x; }\n namespace foo { }\n'


def test_new_reformatting_arg1(input_path, external_programs):
    write_file(input_path, 'int f() {\nchar x;\n}\nnamespace foo\n{\n}\n')
    p = LinesPass('1', external_programs)
    p.new(input_path, check_sanity=lambda: True)
    assert read_file(input_path) == 'int f() {\n char x;\n }\n namespace foo {\n }\n'


def test_transform_deletes_individual_line(input_path, external_programs):
    write_file(input_path, 'int f() { char x; }\nnamespace foo { }\n')
    p = LinesPass('0', external_programs)
    state = p.new(input_path)
    all_transforms = collect_all_transforms(p, state, input_path)
    assert 'int f() { char x; }\n' in all_transforms
    assert ' namespace foo { }\n' in all_transforms


def test_transform_deletes_lines_range(input_path, external_programs):
    write_file(input_path, 'A;\nB;\nC;\nD;\nE;\nF;\nG;\nH;\n')
    p = LinesPass('0', external_programs)
    state = p.new(input_path)
    all_transforms = collect_all_transforms(p, state, input_path)
    # deletion of a half:
    assert 'A;\n B;\n C;\n D;\n' in all_transforms
    assert ' E;\n F;\n G;\n H;\n' in all_transforms
    # deletion of a quarter:
    assert ' C;\n D;\n E;\n F;\n G;\n H;\n' in all_transforms
    assert 'A;\n B;\n E;\n F;\n G;\n H;\n' in all_transforms
    assert 'A;\n B;\n C;\n D;\n G;\n H;\n' in all_transforms
    assert 'A;\n B;\n C;\n D;\n E;\n F;\n' in all_transforms


def test_advance_on_success(input_path, external_programs):
    write_file(input_path, 'foo;\nbar;\nbaz;\n')
    p = LinesPass('0', external_programs)
    state = p.new(input_path)
    # cut 'foo' first
    state = advance_until(p, state, input_path, lambda s: 'bar' in s and 'baz' in s)
    p.advance_on_success(input_path, state)
    # cut 'baz' now
    state = advance_until(p, state, input_path, lambda s: 'bar' in s)
    p.advance_on_success(input_path, state)
    assert read_file(input_path) == ' bar;\n'

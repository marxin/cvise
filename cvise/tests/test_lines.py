import pytest

from cvise.passes.lines import LinesPass
from cvise.tests.testabstract import collect_all_transforms
from cvise.utils.error import InsaneTestCaseError
from cvise.utils.externalprograms import find_external_programs


@pytest.fixture
def input_path(tmp_path):
    return tmp_path / 'input.cc'


def init_pass(depth, input_path, check_sanity):
    pass_ = LinesPass(depth, find_external_programs())
    state = pass_.new(input_path, check_sanity=check_sanity)
    return pass_, state


def read_file(path):
    with open(path) as f:
        return f.read()


def write_file(path, data):
    with open(path, 'w') as f:
        f.write(data)


def advance_until(pass_, state, input_path, predicate):
    backup = read_file(input_path)
    while True:
        pass_.transform(input_path, state, process_event_notifier=None)
        if predicate(read_file(input_path)):
            return state
        write_file(input_path, backup)
        state = pass_.advance(input_path, state)
        assert state is not None


def test_func_namespace_level0(input_path):
    """Test that arg=0 deletes top-level functions and namespaces."""
    write_file(input_path, 'int f() {\nchar x;\n}\nnamespace foo\n{\n}\n')
    p, state = init_pass('0', input_path, check_sanity=lambda: True)
    all_transforms = collect_all_transforms(p, state, input_path)
    # removal of the namespace
    assert 'int f() { char x; }\n' in all_transforms
    # removal of f()
    assert 'namespace foo { }\n' in all_transforms


def test_func_namespace_level1(input_path):
    """Test that arg=1 deletes code inside top-level functions and namespaces."""
    write_file(input_path, 'int f() {\nchar x;\n}\nnamespace foo\n{\nvoid g() {\n}\n}\n')
    p, state = init_pass('1', input_path, check_sanity=lambda: True)
    all_transforms = collect_all_transforms(p, state, input_path)
    # removal of code inside f()
    assert 'int f() {\n}\nnamespace foo {\nvoid g() { }\n}\n' in all_transforms
    # removal of code inside foo
    assert 'int f() {\nchar x;\n}\nnamespace foo {\n}\n' in all_transforms


def test_multiline_func_signature_level0(input_path):
    """Test that arg=0 deletes a top-level function despite line breaks in the signature."""
    write_file(input_path, 'template <class T>\nint\nf()\n{\n}')
    p, state = init_pass('0', input_path, check_sanity=lambda: True)
    all_transforms = collect_all_transforms(p, state, input_path)
    assert '' in all_transforms
    # no attempts to partially remove the function
    assert len(all_transforms) == 1


def test_multiline_func_signature_level1(input_path):
    """Test that arg=1 deletes a nested function despite line breaks in the signature."""
    write_file(input_path, 'namespace {\ntemplate <class T>\nint\nf()\n{\n}\n}\n')
    p, state = init_pass('1', input_path, check_sanity=lambda: True)
    all_transforms = collect_all_transforms(p, state, input_path)
    assert 'namespace {\n}\n' in all_transforms
    # the (multi-line) func must be deleted as a whole, not partially
    for s in all_transforms:
        assert ('template' in s) == ('f()' in s)


def test_c_comment(input_path):
    """Test that a C comment is deleted as a whole."""
    write_file(input_path, 'int x; /* \nsome\ncomment\n */\nint y;')
    p, state = init_pass('0', input_path, check_sanity=lambda: True)
    all_transforms = collect_all_transforms(p, state, input_path)
    assert 'int x;\nint y;\n' in all_transforms
    # no attempts to partially remove the comment
    for s in all_transforms:
        assert ('/*' in s) == ('some' in s) == ('comment' in s) == ('*/' in s)


def test_cpp_comment(input_path):
    """Test that a C++ comment is deleted as a whole."""
    write_file(input_path, 'int x; // some comment\nint y;')
    p, state = init_pass('0', input_path, check_sanity=lambda: True)
    all_transforms = collect_all_transforms(p, state, input_path)
    assert 'int x;\nint y;\n' in all_transforms
    # no attempts to partially remove the comment
    for s in all_transforms:
        assert ('//' in s) == ('some' in s) == ('comment' in s)


def test_transform_deletes_lines_range(input_path):
    """Test various combinations of line deletion are attempted.

    This verifies the code performs the binary search or some similar strategy."""
    write_file(input_path, 'A;\nB;\nC;\nD;\nE;\nF;\nG;\nH;\n')
    p, state = init_pass('0', input_path, check_sanity=lambda: True)
    all_transforms = collect_all_transforms(p, state, input_path)
    # deletion of a half:
    assert 'A;\nB;\nC;\nD;\n' in all_transforms
    assert 'E;\nF;\nG;\nH;\n' in all_transforms
    # deletion of a quarter:
    assert 'C;\nD;\nE;\nF;\nG;\nH;\n' in all_transforms
    assert 'A;\nB;\nE;\nF;\nG;\nH;\n' in all_transforms
    assert 'A;\nB;\nC;\nD;\nG;\nH;\n' in all_transforms
    assert 'A;\nB;\nC;\nD;\nE;\nF;\n' in all_transforms


def test_advance_on_success(input_path):
    """Test the scenario where successful advancements are interleaved with unsuccessful transforms."""
    write_file(input_path, 'foo;\nbar;\nbaz;\n')
    p, state = init_pass('0', input_path, check_sanity=lambda: True)
    # cut 'foo' first
    state = advance_until(p, state, input_path, lambda s: 'bar' in s and 'baz' in s)
    p.advance_on_success(input_path, state)
    # cut 'baz' now
    state = advance_until(p, state, input_path, lambda s: 'bar' in s)
    p.advance_on_success(input_path, state)
    assert read_file(input_path) == 'bar;\n'


def test_new_reformatting_keeps_spaces_if_needed(input_path):
    """Test the fallback scenario, when trimming spaces leads to an unsuccessful sanity check."""

    def check_sanity():
        if '  char' not in read_file(input_path):
            raise InsaneTestCaseError([], '')

    write_file(input_path, 'int f() {\n  char x;}\n')
    p, _ = init_pass('1', input_path, check_sanity)
    assert read_file(input_path) == 'int f() {\n   char x;\n}\n'

import pytest

from cvise.passes.lines import LinesPass
from cvise.tests.testabstract import collect_all_transforms
from cvise.utils.externalprograms import find_external_programs


@pytest.fixture
def input_path(tmp_path):
    return tmp_path / 'input.cc'


def init_pass(depth, tmp_dir, input_path):
    pass_ = LinesPass(depth, find_external_programs())
    state = pass_.new(input_path, tmp_dir=tmp_dir)
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


def is_valid_brace_sequence(s):
    balance = 0
    for c in s:
        if c == '{':
            balance += 1
        elif c == '}':
            balance -= 1
        if balance < 0:
            return False
    return balance == 0


def test_func_namespace_level0(tmp_path, input_path):
    """Test that arg=0 deletes top-level functions and namespaces."""
    write_file(
        input_path,
        """
        int f() {
          char x;
        }
        namespace foo {
        }""",
    )
    p, state = init_pass('0', tmp_path, input_path)
    all_transforms = collect_all_transforms(p, state, input_path)

    # removal of the namespace
    assert (
        """
        int f() {
          char x;
        }"""
        in all_transforms
    )
    # removal of f()
    assert (
        """
        namespace foo {
        }"""
        in all_transforms
    )
    # check no transform violates curly brace sequences
    for s in all_transforms:
        assert is_valid_brace_sequence(s)


def test_func_namespace_level1(tmp_path, input_path):
    """Test that arg=1 deletes code inside top-level functions and namespaces."""
    write_file(
        input_path,
        """
        int f() {
          char x;
        }
        namespace foo {
          void g() {
          }
        }
        """,
    )
    p, state = init_pass('1', tmp_path, input_path)
    all_transforms = collect_all_transforms(p, state, input_path)

    # removal of code inside f()
    assert (
        """
        int f() {
        }
        namespace foo {
          void g() {
          }
        }
        """
        in all_transforms
    )
    # removal of code inside foo
    assert (
        """
        int f() {
          char x;
        }
        namespace foo {
        }
        """
        in all_transforms
    )
    # removal of both
    assert (
        """
        int f() {
        }
        namespace foo {
        }
        """
        in all_transforms
    )
    # check no transform violates curly brace sequences
    for s in all_transforms:
        assert is_valid_brace_sequence(s)


def test_multiline_func_signature_level0(tmp_path, input_path):
    """Test that arg=0 deletes a top-level function despite line breaks in the signature."""
    write_file(
        input_path,
        """
        template <class T>
        SomeVeryLongType
        f()
        {
        }""",
    )
    p, state = init_pass('0', tmp_path, input_path)
    all_transforms = collect_all_transforms(p, state, input_path)

    assert '' in all_transforms
    # no attempts to partially remove the function
    assert len(all_transforms) == 1
    # check no transform violates curly brace sequences
    for s in all_transforms:
        assert is_valid_brace_sequence(s)


def test_multiline_func_signature_level1(tmp_path, input_path):
    """Test that arg=1 deletes a nested function despite line breaks in the signature."""
    write_file(
        input_path,
        """
        namespace {
          template <class T>
          SomeVeryLongType
          f()
          {
          }
        }""",
    )
    p, state = init_pass('1', tmp_path, input_path)
    all_transforms = collect_all_transforms(p, state, input_path)

    assert (
        """
        namespace {
        }"""
        in all_transforms
    )
    # the (multi-line) func must be deleted as a whole, not partially
    # FIXME: Improve the heuristic to not try removing just the opening `namespace {` part,
    # and replace the assertion here with "len(all_transforms) == 1".
    for s in all_transforms:
        assert ('template' in s) == ('f()' in s)
    # check no transform violates curly brace sequences
    for s in all_transforms:
        assert is_valid_brace_sequence(s)


def test_class_with_methods_level0(tmp_path, input_path):
    """Test that arg=0 deletes the whole class definition."""
    write_file(
        input_path,
        """
        class A {
          void f() {
            int first;
            int second;
          }
          int g() {
            return 42;
          }
        };
        """,
    )
    p, state = init_pass('0', tmp_path, input_path)
    all_transforms = collect_all_transforms(p, state, input_path)

    assert '' in all_transforms
    # check no transform violates curly brace sequences
    for s in all_transforms:
        assert is_valid_brace_sequence(s)


def test_class_with_methods_level1(tmp_path, input_path):
    """Test that arg=1 deletes class methods."""
    write_file(
        input_path,
        """
        class A {
          void f() {
            int first;
            int second;
          }
          int g() {
            return 42;
          }
        };
        """,
    )
    p, state = init_pass('1', tmp_path, input_path)
    all_transforms = collect_all_transforms(p, state, input_path)

    # f() deleted
    assert (
        """
        class A {
          int g() {
            return 42;
          }
        };
        """
        in all_transforms
    )
    # g() deleted
    assert (
        """
        class A {
          void f() {
            int first;
            int second;
          }
        };
        """
        in all_transforms
    )
    # both f() and g() deleted
    assert (
        """
        class A {
        };
        """
        in all_transforms
    )
    # check no transform violates curly brace sequences
    for s in all_transforms:
        assert is_valid_brace_sequence(s)


def test_class_with_methods_level2(tmp_path, input_path):
    """Test that arg=2 deletes statements in class methods."""
    write_file(
        input_path,
        """
        class A {
          void f() {
            int first;
            int second;
          }
          int g() {
            return 42;
          }
        };
        """,
    )
    p, state = init_pass('2', tmp_path, input_path)
    all_transforms = collect_all_transforms(p, state, input_path)

    # the first statement in f() deleted
    assert (
        """
        class A {
          void f() {
            int second;
          }
          int g() {
            return 42;
          }
        };
        """
        in all_transforms
    )
    # the second statement in f() deleted
    assert (
        """
        class A {
          void f() {
            int first;
          }
          int g() {
            return 42;
          }
        };
        """
        in all_transforms
    )
    # the statement in g() deleted
    assert (
        """
        class A {
          void f() {
            int first;
            int second;
          }
          int g() {
          }
        };
        """
        in all_transforms
    )
    # all statements in f() and g() deleted
    assert (
        """
        class A {
          void f() {
          }
          int g() {
          }
        };
        """
        in all_transforms
    )
    # check no transform violates curly brace sequences
    for s in all_transforms:
        assert is_valid_brace_sequence(s)


def test_c_comment(tmp_path, input_path):
    """Test that a C comment is deleted as a whole."""
    write_file(
        input_path,
        """
        int x; /*
          some
          comment
          */
        int y;
        """,
    )
    p, state = init_pass('0', tmp_path, input_path)
    all_transforms = collect_all_transforms(p, state, input_path)

    assert (
        """
        int x;
        """
        in all_transforms
    )
    assert (
        """ /*
          some
          comment
          */
        int y;
        """
        in all_transforms
    )
    # no attempts to partially remove the comment
    for s in all_transforms:
        assert ('/*' in s) == ('some' in s) == ('comment' in s) == ('*/' in s)


def test_cpp_comment(tmp_path, input_path):
    """Test that a C++ comment is deleted as a whole."""
    write_file(
        input_path,
        """
        int x; // some comment
        int y;
        """,
    )
    p, state = init_pass('0', tmp_path, input_path)
    all_transforms = collect_all_transforms(p, state, input_path)

    assert (
        """
        int x;
        """
        in all_transforms
    )
    assert (
        """ // some comment
        int y;
        """
        in all_transforms
    )
    # no attempts to partially remove the comment
    for s in all_transforms:
        assert ('//' in s) == ('some' in s) == ('comment' in s)


def test_eof_with_non_recognized_chunk_end(tmp_path, input_path):
    """Test the file terminating with a text that wouldn't be recognized as chunk end."""
    write_file(
        input_path,
        """
        #define FOO }
        FOO
        """,
    )
    p, state = init_pass('0', tmp_path, input_path)
    all_transforms = collect_all_transforms(p, state, input_path)

    # FOO was attempted to be deleted
    assert (
        """
        #define FOO }
"""
        in all_transforms
    )


def test_transform_deletes_lines_range(tmp_path, input_path):
    """Test various combinations of line deletion are attempted.

    This verifies the code performs the binary search or some similar strategy."""
    write_file(
        input_path,
        """
        A;
        B;
        C;
        D;
        E;
        F;
        G;
        H;
        """,
    )
    p, state = init_pass('0', tmp_path, input_path)
    all_transforms = collect_all_transforms(p, state, input_path)

    # deletion of a half:
    assert (
        """
        A;
        B;
        C;
        D;
        """
        in all_transforms
    )
    assert (
        """
        E;
        F;
        G;
        H;
        """
        in all_transforms
    )
    # deletion of a quarter:
    assert (
        """
        C;
        D;
        E;
        F;
        G;
        H;
        """
        in all_transforms
    )
    assert (
        """
        A;
        B;
        E;
        F;
        G;
        H;
        """
        in all_transforms
    )
    assert (
        """
        A;
        B;
        C;
        D;
        G;
        H;
        """
        in all_transforms
    )
    assert (
        """
        A;
        B;
        C;
        D;
        E;
        F;
        """
        in all_transforms
    )


def test_advance_on_success(tmp_path, input_path):
    """Test the scenario where successful advancements are interleaved with unsuccessful transforms."""
    write_file(
        input_path,
        """
        foo;
        bar;
        baz;
        """,
    )
    p, state = init_pass('0', tmp_path, input_path)
    # Cut 'foo' first, pretending that all previous transforms (e.g., deletion of the whole text) didn't pass the
    # interestingness test.
    state = advance_until(p, state, input_path, lambda s: 'bar' in s and 'baz' in s)
    p.advance_on_success(input_path, state)
    # Cut 'baz' now, pretending that all transforms in between (e.g, deletion of "bar;") didn't pass the
    # interestingness test.
    state = advance_until(p, state, input_path, lambda s: 'bar' in s)
    p.advance_on_success(input_path, state)

    assert (
        read_file(input_path)
        == """
        bar;
        """
    )

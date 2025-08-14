from pathlib import Path
import pytest
from typing import Any, Tuple

from cvise.passes.lines import LinesPass
from cvise.tests.testabstract import collect_all_transforms, validate_stored_hints
from cvise.utils.externalprograms import find_external_programs


@pytest.fixture
def input_path(tmp_path: Path) -> Path:
    return tmp_path / 'input.cc'


def init_pass(depth, tmp_dir: Path, input_path: Path) -> Tuple[LinesPass, Any]:
    pass_ = LinesPass(depth, find_external_programs())
    state = pass_.new(input_path, tmp_dir=tmp_dir)
    validate_stored_hints(state)
    return pass_, state


def advance_until(pass_, state, input_path: Path, predicate):
    backup = input_path.read_bytes()
    while True:
        pass_.transform(input_path, state, process_event_notifier=None, original_test_case=input_path)
        if predicate(input_path.read_bytes()):
            return state
        input_path.write_bytes(backup)
        state = pass_.advance(input_path, state)
        assert state is not None


def is_valid_brace_sequence(s: bytes) -> bool:
    balance = 0
    for c in s:
        if c == ord('{'):
            balance += 1
        elif c == ord('}'):
            balance -= 1
        if balance < 0:
            return False
    return balance == 0


def test_func_namespace_level0(tmp_path: Path, input_path: Path):
    """Test that arg=0 deletes top-level functions and namespaces."""
    input_path.write_text(
        """
        int f() {
          char x;
        }
        namespace foo {
        }
        """,
    )
    p, state = init_pass('0', tmp_path, input_path)
    all_transforms = collect_all_transforms(p, state, input_path)

    # removal of the namespace
    assert (
        b"""
        int f() {
          char x;
        }
        """
        in all_transforms
    )
    # removal of f()
    assert (
        b"""
        namespace foo {
        }
        """
        in all_transforms
    )
    # check no transform violates curly brace sequences
    for s in all_transforms:
        assert is_valid_brace_sequence(s)


def test_func_namespace_level1(tmp_path: Path, input_path: Path):
    """Test that arg=1 deletes code inside top-level functions and namespaces."""
    input_path.write_text(
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
        b"""
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
        b"""
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
        b"""
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


def test_multiline_func_signature_level0(tmp_path: Path, input_path: Path):
    """Test that arg=0 deletes a top-level function despite line breaks in the signature."""
    input_path.write_text(
        """
        template <class T>
        SomeVeryLongType
        f()
        {
        }""",
    )
    p, state = init_pass('0', tmp_path, input_path)
    all_transforms = collect_all_transforms(p, state, input_path)

    assert b'' in all_transforms
    # no attempts to partially remove the function
    assert len(all_transforms) == 1


def test_multiline_func_signature_level1(tmp_path: Path, input_path: Path):
    """Test that arg=1 deletes a nested function despite line breaks in the signature."""
    input_path.write_text(
        """
        namespace {
          template <class T>
          SomeVeryLongType
          f()
          {
          }
        }
        """,
    )
    p, state = init_pass('1', tmp_path, input_path)
    all_transforms = collect_all_transforms(p, state, input_path)

    assert (
        b"""
        namespace {
        }
        """
        in all_transforms
    )
    # the (multi-line) func must be deleted as a whole, not partially
    assert len(all_transforms) == 1


def test_class_with_methods_level0(tmp_path: Path, input_path: Path):
    """Test that arg=0 deletes the whole class definition."""
    input_path.write_text(
        """
        class A {
          void f() {
            int first;
            int second;
          }
          int g() {
            return 42;
          }
        };""",
    )
    p, state = init_pass('0', tmp_path, input_path)
    all_transforms = collect_all_transforms(p, state, input_path)

    assert b'' in all_transforms
    assert len(all_transforms) == 1


def test_class_with_methods_level1(tmp_path: Path, input_path: Path):
    """Test that arg=1 deletes class methods."""
    input_path.write_text(
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
        b"""
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
        b"""
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
        b"""
        class A {
        };
        """
        in all_transforms
    )
    # check no transform violates curly brace sequences
    for s in all_transforms:
        assert is_valid_brace_sequence(s)


def test_class_with_methods_level2(tmp_path: Path, input_path: Path):
    """Test that arg=2 deletes statements in class methods."""
    input_path.write_text(
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
        b"""
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
        b"""
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
        b"""
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
        b"""
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


def test_c_comment(tmp_path: Path, input_path: Path):
    """Test that a C comment is deleted as a whole."""
    input_path.write_text(
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
        b"""
        int x;
        """
        in all_transforms
    )
    assert (
        b""" /*
          some
          comment
          */
        int y;
        """
        in all_transforms
    )
    # no attempts to partially remove the comment
    for s in all_transforms:
        assert (b'/*' in s) == (b'some' in s) == (b'comment' in s) == (b'*/' in s)


def test_cpp_comment(tmp_path: Path, input_path: Path):
    """Test that a C++ comment is deleted as a whole."""
    input_path.write_text(
        """
        int x; // some comment
        int y;""",
    )
    p, state = init_pass('0', tmp_path, input_path)
    all_transforms = collect_all_transforms(p, state, input_path)

    # no attempts to partially remove the comment
    assert (
        b"""
        int x;"""
        in all_transforms
    )
    assert (
        b""" // some comment
        int y;"""
        in all_transforms
    )
    assert b'' in all_transforms
    assert len(all_transforms) == 3


def test_eof_with_non_recognized_chunk_end(tmp_path: Path, input_path: Path):
    """Test the file terminating with a text that wouldn't be recognized as chunk end."""
    input_path.write_text(
        """
        #define FOO }
        FOO
        """,
    )
    p, state = init_pass('0', tmp_path, input_path)
    all_transforms = collect_all_transforms(p, state, input_path)

    # FOO was attempted to be deleted
    assert (
        b"""
        #define FOO }
"""
        in all_transforms
    )


def test_macro_level0(tmp_path: Path, input_path: Path):
    """Test removal of preprocessor macros with arg=0."""
    input_path.write_text(
        """#ifndef FOO
        #define FOO
        int x;
        FOO
        #define BAR \\
          FOO 42
        int y;
        """,
    )
    p, state = init_pass('0', tmp_path, input_path)
    all_transforms = collect_all_transforms(p, state, input_path)

    # "#ifndef FOO" deleted
    assert (
        b"""
        #define FOO
        int x;
        FOO
        #define BAR \\
          FOO 42
        int y;
        """
        in all_transforms
    )
    # "#define FOO" deleted
    assert (
        b"""#ifndef FOO
        int x;
        FOO
        #define BAR \\
          FOO 42
        int y;
        """
        in all_transforms
    )
    # "int x" deleted
    assert (
        b"""#ifndef FOO
        #define FOO

        FOO
        #define BAR \\
          FOO 42
        int y;
        """
        in all_transforms
    )
    # FOO usage deleted
    assert (
        b"""#ifndef FOO
        #define FOO
        int x;
        #define BAR \\
          FOO 42
        int y;
        """
        in all_transforms
    )
    # "#define BAR" deleted
    assert (
        b"""#ifndef FOO
        #define FOO
        int x;
        FOO
        int y;
        """
        in all_transforms
    )
    # "int y" deleted
    assert (
        b"""#ifndef FOO
        #define FOO
        int x;
        FOO
        #define BAR \\
          FOO 42

        """
        in all_transforms
    )


def test_nested_macro_level0(tmp_path: Path, input_path: Path):
    """Test removal of preprocessor macros, placed inside a curly brace block, with arg=0."""
    input_path.write_text(
        """
        class A {
        #define AFIELD foo
          AFIELD
        #undef AFIELD
        };""",
    )
    p, state = init_pass('0', tmp_path, input_path)
    all_transforms = collect_all_transforms(p, state, input_path)

    # The macro is removed together with the outer block.
    assert b'' in all_transforms
    assert len(all_transforms) == 1


def test_nested_macro_level1(tmp_path: Path, input_path: Path):
    """Test removal of preprocessor macros, placed inside a curly brace block, with arg=1."""
    input_path.write_text(
        """
        class A {
        #define AFIELD foo
          AFIELD
        #undef AFIELD
        };
        """,
    )
    p, state = init_pass('1', tmp_path, input_path)
    all_transforms = collect_all_transforms(p, state, input_path)

    # "#define AFIELD" deleted
    assert (
        b"""
        class A {
          AFIELD
        #undef AFIELD
        };
        """
        in all_transforms
    )
    # AFIELD usage deleted
    assert (
        b"""
        class A {
        #define AFIELD foo

        #undef AFIELD
        };
        """
        in all_transforms
    )
    # "#undef AFIELD" deleted
    assert (
        b"""
        class A {
        #define AFIELD foo
          AFIELD
        };
        """
        in all_transforms
    )


def test_hash_character_not_macro_start(tmp_path: Path, input_path: Path):
    """Test hash characters aren't mistakenly treated as macro/block start."""
    input_path.write_text(
        """
        #define STR(x)  #x
        #define FOO(a,b)  a ## b
        char s[] = "#1";
        """,
    )
    p, state = init_pass('0', tmp_path, input_path)
    all_transforms = collect_all_transforms(p, state, input_path)

    # "#define STR" removed
    assert (
        b"""
        #define FOO(a,b)  a ## b
        char s[] = "#1";
        """
        in all_transforms
    )
    # "#define FOO" removed
    assert (
        b"""
        #define STR(x)  #x
        char s[] = "#1";
        """
        in all_transforms
    )
    # "char s" removed
    assert (
        b"""
        #define STR(x)  #x
        #define FOO(a,b)  a ## b

        """
        in all_transforms
    )


def test_transform_deletes_lines_range(tmp_path: Path, input_path: Path):
    """Test various combinations of line deletion are attempted.

    This verifies the code performs the binary search or some similar strategy."""
    input_path.write_text(
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
        b"""
        A;
        B;
        C;
        D;
        """
        in all_transforms
    )
    assert (
        b"""
        E;
        F;
        G;
        H;
        """
        in all_transforms
    )
    # deletion of a quarter:
    assert (
        b"""
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
        b"""
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
        b"""
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
        b"""
        A;
        B;
        C;
        D;
        E;
        F;
        """
        in all_transforms
    )


def test_advance_on_success(tmp_path: Path, input_path: Path):
    """Test the scenario where successful advancements are interleaved with unsuccessful transforms."""
    input_path.write_text(
        """
        foo;
        bar;
        baz;
        """,
    )
    p, state = init_pass('0', tmp_path, input_path)
    # Cut 'foo' first, pretending that all previous transforms (e.g., deletion of the whole text) didn't pass the
    # interestingness test.
    state = advance_until(p, state, input_path, lambda s: b'bar' in s and b'baz' in s)
    p.advance_on_success(input_path, state)
    # Cut 'baz' now, pretending that all transforms in between (e.g, deletion of "bar;") didn't pass the
    # interestingness test.
    state = advance_until(p, state, input_path, lambda s: b'bar' in s)
    p.advance_on_success(input_path, state)

    assert (
        input_path.read_bytes()
        == b"""
        bar;
        """
    )


def test_arg_none(tmp_path: Path, input_path: Path):
    """Test that arg=None deletes individual lines as-is."""
    input_path.write_text(
        """
        int f() {
        }

        int x = 1;
        """,
    )
    p, state = init_pass('None', tmp_path, input_path)
    all_transforms = collect_all_transforms(p, state, input_path)

    assert (
        b"""
        }

        int x = 1;
        """
        in all_transforms
    )
    assert (
        b"""
        int f() {

        int x = 1;
        """
        in all_transforms
    )
    assert (
        b"""
        int f() {
        }
        int x = 1;
        """
        in all_transforms
    )
    assert (
        b"""
        int f() {
        }

        """
        in all_transforms
    )


@pytest.mark.parametrize('pass_arg', [0, 'None'])
def test_non_ascii(tmp_path: Path, input_path: Path, pass_arg):
    input_path.write_bytes(
        b"""
        char *s = "Streichholzsch\xc3\xa4chtelchen";
        char t[] = "nonutf\xff";
        """,
    )
    p, state = init_pass(str(pass_arg), tmp_path, input_path)
    all_transforms = collect_all_transforms(p, state, input_path)

    assert (
        b"""
        char *s = "Streichholzsch\xc3\xa4chtelchen";
        """
        in all_transforms
    )
    assert (
        b"""
        char t[] = "nonutf\xff";
        """
        in all_transforms
    )

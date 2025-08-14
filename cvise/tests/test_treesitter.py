from pathlib import Path
import pytest
from typing import Any, Tuple

from cvise.passes.treesitter import TreeSitterPass
from cvise.tests.testabstract import collect_all_transforms, validate_stored_hints
from cvise.utils.externalprograms import find_external_programs


REPLACE_FUNC_DEF = 'replace-function-def-with-decl'
ERASE_NAMESPACE = 'erase-namespace'
REMOVE_FUNCTION = 'remove-function'


@pytest.fixture
def input_path(tmp_path: Path) -> Path:
    return tmp_path / 'input.cc'


def init_pass(arg, tmp_dir: Path, input_path: Path) -> Tuple[TreeSitterPass, Any]:
    pass_ = TreeSitterPass(arg, find_external_programs())
    state = pass_.new(input_path, tmp_dir=tmp_dir)
    validate_stored_hints(state)
    return pass_, state


def test_func_def_simple(tmp_path: Path, input_path: Path):
    """Test basic cases for the removal of function bodies."""
    input_path.write_text(
        """
        void f() {
          char x;
        }
        namespace foo {
          const int g(int a, int b) {
            return x;
          }
        }
        """,
    )
    p, state = init_pass(REPLACE_FUNC_DEF, tmp_path, input_path)
    all_transforms = collect_all_transforms(p, state, input_path)

    assert (
        b"""
        void f() ;
        namespace foo {
          const int g(int a, int b) {
            return x;
          }
        }
        """
        in all_transforms
    )
    assert (
        b"""
        void f() {
          char x;
        }
        namespace foo {
          const int g(int a, int b) ;
        }
        """
        in all_transforms
    )
    assert (
        b"""
        void f() ;
        namespace foo {
          const int g(int a, int b) ;
        }
        """
        in all_transforms
    )
    assert len(all_transforms) == 3


def test_func_def_class_method(tmp_path: Path, input_path: Path):
    """Test removal of class methods or their bodies."""
    input_path.write_text(
        """
        class A {
          void foo();
          void bar() {
          }
          void outofline();
        };
        void A::outofline() {
        }
        """,
    )
    p, state = init_pass(REPLACE_FUNC_DEF, tmp_path, input_path)
    all_transforms = collect_all_transforms(p, state, input_path)

    assert (
        b"""
        class A {
          void foo();
          void bar() ;
          void outofline();
        };
        void A::outofline() {
        }
        """
        in all_transforms
    )
    # out-of-line member definition is deleted altogether
    assert (
        b"""
        class A {
          void foo();
          void bar() {
          }
          void outofline();
        };
        \n        """
        in all_transforms
    )


def test_func_def_class_constructor(tmp_path: Path, input_path: Path):
    """Test removal of constructors or their bodies."""
    input_path.write_text(
        """
        class A {
          A();
          A(char) : x(1) {}
          A(int);
          A(long);
        };
        A::A(int) {}
        A::A(long) : x(2) {}
        """,
    )
    p, state = init_pass(REPLACE_FUNC_DEF, tmp_path, input_path)
    all_transforms = collect_all_transforms(p, state, input_path)

    assert (
        b"""
        class A {
          A();
          A(char) ;
          A(int);
          A(long);
        };
        A::A(int) {}
        A::A(long) : x(2) {}
        """
        in all_transforms
    )
    # out-of-line constructors are deleted altogether
    assert (
        b"""
        class A {
          A();
          A(char) : x(1) {}
          A(int);
          A(long);
        };
        \n        A::A(long) : x(2) {}
        """
        in all_transforms
    )
    assert (
        b"""
        class A {
          A();
          A(char) : x(1) {}
          A(int);
          A(long);
        };
        A::A(int) {}
        \n        """
        in all_transforms
    )


def test_func_def_class_destructor(tmp_path: Path, input_path: Path):
    """Test removal of destructors or their bodies."""
    input_path.write_text(
        """
        class A {
          ~A() {}
        };
        class B {
          ~B();
        };
        B::~B() {}
        """,
    )
    p, state = init_pass(REPLACE_FUNC_DEF, tmp_path, input_path)
    all_transforms = collect_all_transforms(p, state, input_path)

    assert (
        b"""
        class A {
          ~A() ;
        };
        class B {
          ~B();
        };
        B::~B() {}
        """
        in all_transforms
    )
    # out-of-line destructor is deleted altogether
    assert (
        b"""
        class A {
          ~A() {}
        };
        class B {
          ~B();
        };
        \n        """
        in all_transforms
    )


def test_func_def_regular_and_template_mix(tmp_path: Path, input_path: Path):
    """Test removals of template functions are tackled separately from other functions."""
    input_path.write_text(
        """
        void f() {}

        template <typename T>
        void g() {}

        void h() {}

        template <typename T>
        void k() {}
        """,
    )
    p, state = init_pass(REPLACE_FUNC_DEF, tmp_path, input_path)
    all_transforms = collect_all_transforms(p, state, input_path)

    # Regular functions considered in one job.
    assert (
        b"""
        void f() ;

        template <typename T>
        void g() {}

        void h() ;

        template <typename T>
        void k() {}
        """
        in all_transforms
    )
    # Template functions considered in another job.
    assert (
        b"""
        void f() {}

        template <typename T>
        void g() ;

        void h() {}

        template <typename T>
        void k() ;
        """
        in all_transforms
    )


def test_func_def_template(tmp_path: Path, input_path: Path):
    """Test removal of template functions or their bodies."""
    input_path.write_text(
        """
        template <typename T>
        void f() {}

        class A {
          template <typename T>
          void g() {}
          template <typename T>
          void h();
        };

        template <typename U>
        class B {
          void m();
          template <typename T>
          void n();
        };

        template <typename T>
        void A::h() {}

        template <typename U>
        void B::m() {}

        template <typename U>
        template <typename T>
        void B::n() {}
        """,
    )
    p, state = init_pass(REPLACE_FUNC_DEF, tmp_path, input_path)
    all_transforms = collect_all_transforms(p, state, input_path)

    # Just check all transforms being applied at once, for brevity.
    assert (
        b"""
        template <typename T>
        void f() ;

        class A {
          template <typename T>
          void g() ;
          template <typename T>
          void h();
        };

        template <typename U>
        class B {
          void m();
          template <typename T>
          void n();
        };

        \n
        \n
        \n        """
        in all_transforms
    )


def test_func_def_constexpr(tmp_path: Path, input_path: Path):
    """Test no removal happens for constexpr function bodies."""
    input_path.write_text(
        """
        constexpr int f() {
          return 42;
        }
        constexpr const int g() {
          return x;
        }
        """,
    )
    p, state = init_pass(REPLACE_FUNC_DEF, tmp_path, input_path)
    all_transforms = collect_all_transforms(p, state, input_path)

    assert all_transforms == set()


def test_func_erase_namespace(tmp_path: Path, input_path: Path):
    """Test the basic case for the removal of namespace contents."""
    input_path.write_text(
        """
        namespace foo {
        int x;
        }
        int y;
        namespace {
        int z;
        }
        """,
    )
    p, state = init_pass(ERASE_NAMESPACE, tmp_path, input_path)
    all_transforms = collect_all_transforms(p, state, input_path)

    assert (
        b"""
        namespace foo {}
        int y;
        namespace {
        int z;
        }
        """
        in all_transforms
    )
    assert (
        b"""
        namespace foo {
        int x;
        }
        int y;
        namespace {}
        """
        in all_transforms
    )


def test_func_erase_namespace_nested(tmp_path: Path, input_path: Path):
    """Test the removal of contents of nested namespaces."""
    input_path.write_text(
        """
        namespace foo {
        int x;
        namespace bar {
        int y;
        }
        }
        namespace a::b {
        int z;
        }
        """,
    )
    p, state = init_pass(ERASE_NAMESPACE, tmp_path, input_path)
    all_transforms = collect_all_transforms(p, state, input_path)

    assert (
        b"""
        namespace foo {
        int x;
        namespace bar {}
        }
        namespace a::b {
        int z;
        }
        """
        in all_transforms
    )
    assert (
        b"""
        namespace foo {}
        namespace a::b {
        int z;
        }
        """
        in all_transforms
    )
    assert (
        b"""
        namespace foo {
        int x;
        namespace bar {
        int y;
        }
        }
        namespace a::b {}
        """
        in all_transforms
    )


def test_remove_func(tmp_path: Path, input_path: Path):
    input_path.write_text(
        """
        int f() {
          return 42;
        }
        class A {
          void g() {}
        };
        """,
    )
    p, state = init_pass(REMOVE_FUNCTION, tmp_path, input_path)
    all_transforms = collect_all_transforms(p, state, input_path)

    assert (
        b"""
        \n        class A {
          void g() {}
        };
        """
        in all_transforms
    )
    assert (
        b"""
        int f() {
          return 42;
        }
        class A {
          \n        };
        """
        in all_transforms
    )


def test_remove_func_template(tmp_path: Path, input_path: Path):
    input_path.write_text(
        """
        template <typename T>
        void f() {}
        template <typename U>
        template <typename T>
        void A<U>::g() {}
        """,
    )
    p, state = init_pass(REMOVE_FUNCTION, tmp_path, input_path)
    all_transforms = collect_all_transforms(p, state, input_path)

    assert (
        b"""
        \n        template <typename U>
        template <typename T>
        void A<U>::g() {}
        """
        in all_transforms
    )

    assert (
        b"""
        template <typename T>
        void f() {}
        \n        """
        in all_transforms
    )


def test_remove_func_special(tmp_path: Path, input_path: Path):
    input_path.write_text(
        """
        class A {
          A() {}
          ~A() {}
        };
        """,
    )
    p, state = init_pass(REMOVE_FUNCTION, tmp_path, input_path)
    all_transforms = collect_all_transforms(p, state, input_path)

    assert (
        b"""
        class A {
          \n          ~A() {}
        };
        """
        in all_transforms
    )
    assert (
        b"""
        class A {
          A() {}
          \n        };
        """
        in all_transforms
    )


def test_remove_func_outofline(tmp_path: Path, input_path: Path):
    input_path.write_text(
        """
        class A {
          void f();
          class B {
            void g();
          };
        };
        void A::f() {}
        void A::B::g() {}
        """,
    )
    p, state = init_pass(REMOVE_FUNCTION, tmp_path, input_path)
    all_transforms = collect_all_transforms(p, state, input_path)

    assert (
        b"""
        class A {
          \n          class B {
            void g();
          };
        };
        \n        void A::B::g() {}
        """
        in all_transforms
    )
    assert (
        b"""
        class A {
          void f();
          class B {
            \n          };
        };
        void A::f() {}
        \n        """
        in all_transforms
    )


def test_remove_func_grouping_related(tmp_path: Path, input_path: Path):
    """Test that function removal attempts removing all instances of a function with a given name."""
    input_path.write_text(
        """
        class A {
          void f() {}
        };
        void g() {}
        class B : public A {
          void f() {}
        };
        class C {
          class D : public A {
            void f();
          };
        };
        void C::D::f() {}
        """,
    )
    p, state = init_pass(REMOVE_FUNCTION, tmp_path, input_path)
    all_transforms = collect_all_transforms(p, state, input_path)

    assert (
        b"""
        class A {
          \n        };
        void g() {}
        class B : public A {
          \n        };
        class C {
          class D : public A {
            \n          };
        };
        \n        """
        in all_transforms
    )

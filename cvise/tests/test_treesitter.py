import pytest

from cvise.passes.treesitter import TreeSitterPass
from cvise.tests.testabstract import collect_all_transforms, validate_stored_hints
from cvise.utils.externalprograms import find_external_programs


REPLACE_FUNC_DEF = 'replace-function-def-with-decl'


@pytest.fixture
def input_path(tmp_path):
    return tmp_path / 'input.cc'


def init_pass(arg, tmp_dir, input_path):
    pass_ = TreeSitterPass(arg, find_external_programs())
    state = pass_.new(input_path, tmp_dir=tmp_dir)
    validate_stored_hints(state)
    return pass_, state


def test_func_def_simple(tmp_path, input_path):
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


def test_func_def_class_method(tmp_path, input_path):
    """Test removal of class methods."""
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


def test_func_def_class_constructor(tmp_path, input_path):
    """Test removal of constructor bodies."""
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


def test_func_def_class_destructor(tmp_path, input_path):
    """Test removal of destructor bodies."""
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


def test_func_def_template(tmp_path, input_path):
    """Test removal of template function bodies."""
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


def test_func_def_constexpr(tmp_path, input_path):
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

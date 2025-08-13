template <typename T>
struct A {
  struct Inner;
  // This shouldn't be treated as an instance:
  typedef A::Inner Foo;
};

template <class T> struct S { typedef T type; };

struct B {
  struct Inner;
};

template <typename T>
struct C {
  typedef typename S<T>::type::Inner Bar;
};

typedef C<B>::Bar D;

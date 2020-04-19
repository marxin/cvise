struct S1 {};

template<typename T> class Base {
  int foo(S1) {}
};

template<typename Tp, typename T> class S2 : Base<Tp> {
  int foo(S1) {}
};


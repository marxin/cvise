template <typename> struct S1 {
  typedef S1 b;
  void operator<<(b ());
};

template <typename T> S1<T> fun();
S1<char> s;

int foo() {
  s << fun;
}

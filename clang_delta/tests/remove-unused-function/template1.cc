template<typename T> void foo(T *);
template <typename T> struct S {
  template<typename T1> friend void foo(T1 *);
};

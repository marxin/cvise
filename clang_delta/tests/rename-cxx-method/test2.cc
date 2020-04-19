class A {
  template <typename T> static int foo(T, int) {
     foo<T, 0>(0, 0);
  }
};

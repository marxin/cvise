class A {
  template < typename T > void foo (T) { foo <T> (0); }
};

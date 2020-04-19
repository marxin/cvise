struct S {
  int a[2];
};

int foo() {
  struct S s = {1,2};
  return s.a[0];
}

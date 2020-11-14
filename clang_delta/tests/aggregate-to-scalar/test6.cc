struct S {
  int **f1;
};

void foo() {
  int *a[16];
  struct S s = { a };
  s.f1[0] = 0;
}

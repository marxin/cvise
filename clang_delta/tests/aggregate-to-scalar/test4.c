struct S {
 int f1;
 int f2;
};
struct S s = {
  .f1 = 0,
  .f2 = 16
};

void foo() {
  s.f1++;
}

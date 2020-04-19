template <int h>
void foo() {
  double k[1][h];
}
void bar() {
  foo<1>();
}

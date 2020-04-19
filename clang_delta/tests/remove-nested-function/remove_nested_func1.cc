struct S1 {
  S1(int);
};
int foo();
int bar(int);
struct f : S1 {
  f() : S1(bar(foo())) {
    bar(foo());
  }
};

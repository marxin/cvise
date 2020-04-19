class AAA {
public:
  AAA() {}
  static int m1;
};

int AAA::m1;

int foo(void) {
  AAA a1;
  AAA::m1 = 1;
  return 0;
}

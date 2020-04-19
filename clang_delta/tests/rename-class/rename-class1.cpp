class AAA {
public:
  AAA() {}
  static int m1;
};
int AAA::m1;
void foo() {
  AAA a1;
  AAA::m1 = 1;
}


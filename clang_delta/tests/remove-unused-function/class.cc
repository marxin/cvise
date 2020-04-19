class A {
  ~A() {}
  void foo();
};

void A::foo() {
  return;
}

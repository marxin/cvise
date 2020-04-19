struct S {
  S() {
    int t1; int a;
    int b = a;
    {
      m;
      int a = b;
      t1 = a;
    }
  }
  int m;
};

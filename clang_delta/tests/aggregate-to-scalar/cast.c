int a1[10];

void foo() {
  char a;
  int t = 1;
  ((char (*)[t]) a)[0][0] = 0;
  a1[1] = 1;
}

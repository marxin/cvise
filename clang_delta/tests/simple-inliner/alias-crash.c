a[6];
b;
c() __attribute__((alias("func_53")));
d() { c(); }
func_53() {
  for (;; b--) return;
}
e;
main() { d(); }

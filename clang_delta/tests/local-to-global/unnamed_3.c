void f() {
  long i = ({
    union {
      int j;
    } l;
    l.j;
  });
}

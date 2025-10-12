struct A {};
struct A f();
void g(void) {
  struct A a = f();
}

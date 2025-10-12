struct A {};
struct A f();
struct A __trans_tmp_1;
void g(void) {
  struct A a = __trans_tmp_1;
  struct A b = f();
}

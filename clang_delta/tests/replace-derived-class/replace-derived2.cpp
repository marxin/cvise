struct a {
  ~a();
};
struct X : a {} *b;
void foo() {
  b->~X();
}

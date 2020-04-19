struct a {
  ~a();
};
struct X : a {};
void foo() {
   X *b;
   b->~X();
}

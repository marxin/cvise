template <typename T> struct S {
  T bar(T p) { return p; }
};
class T {};
void foo() {
  struct S<T> s;
}

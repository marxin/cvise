// Check that a forward declaration is inserted

template <class a> void b(a&) {
}

struct S {
};

void f() {
  S s;
  b(s);
}

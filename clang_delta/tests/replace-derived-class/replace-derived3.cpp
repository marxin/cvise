struct a {
  ~a();
};
struct abcabcabcabcabcabcabca : a {} *b;
void foo() {
   b->~abcabcabcabcabcabcabca();
}

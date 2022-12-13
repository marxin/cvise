template <class f, class g> void C(f, g) {}

void f() {
	C<int, double>(10, 1.0);
}

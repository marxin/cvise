
class C {
public:
	int& f();
};

void func(C& c1, C& c2) {
	c1.f() = c2.f();
}

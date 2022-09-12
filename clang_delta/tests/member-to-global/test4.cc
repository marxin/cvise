
class C {
public:
	static int s;
};

int C::s = 5;

int func() {
	return C::s;
}

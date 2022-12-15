
namespace ns {
	struct C {
		int test(int hello);
	};
}

// ...

int ns::C::test(int x) {
	return 42;
}

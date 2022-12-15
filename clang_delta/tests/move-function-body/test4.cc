
namespace ns {
	struct C {
		template <class T> 
		T test(T hello);
	};
}

// ...

template <class T> 
T ns::C::test(T x) {
	return 42;
}

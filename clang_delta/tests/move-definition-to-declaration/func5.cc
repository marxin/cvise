
template <class>
struct C {
	template <class T> 
	T test(T hello);
};

// ...

template <class T1> 
template <class T2> 
T2 C<T1>::test(T2 x) {
	return T1();
}

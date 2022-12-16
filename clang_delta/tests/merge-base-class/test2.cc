
template <class T>
struct c1 {
	c1(T x);
	
	// hello
	T y;
};

struct c2 : public c1<int> {
	c2() :  c1<int>(5) {
	}
	
};

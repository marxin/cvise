
template <class T>
struct c1 {
};

template <>
struct c1<int> {
	c1(int x);
	
	// hello
	int y;
};

struct c2 : public c1<int> {
	c2() :  c1<int>(5) {
	}
	
};

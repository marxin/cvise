
struct c1 {
	int x;
	int y;
	
	// hello
	c1(int x);
};

struct c2 : public c1 {
	c2() :  c1(5) {
	}
	
};

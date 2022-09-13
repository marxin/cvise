
class test {
public:
};

test operator + (test&, test);
test operator ~ (test&);
test operator ++ (test&);
test operator ++ (test&, int);

void func() {
	test t1,t2,t3;
	
	t3 = t1 + t2;
	t3 = ~t1;

	++t3;
	t3++;

	operator ~(t3);
	&operator~;
}

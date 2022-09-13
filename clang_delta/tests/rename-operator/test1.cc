
class test {
public:
	test operator + (test);
	test operator ~ ();
	test operator ++ ();
	test operator ++ (int);

	test operator () (int);
	test operator () (int, int);
	test operator () (int, int, int);

	test operator [] (int);
};

test test::operator ~ () {
	return test();
}

void func() {
	test t1,t2,t3;
	
	t3 = t1 + t2;
	t3 = ~t1;

	(t1) [ 0];

	t1(0);
	t1 ( 1, 2 );
	t1  (3, 4, 5 );

	++t3;
	t3++;

	t3.operator ~();
	&test::operator~;
}

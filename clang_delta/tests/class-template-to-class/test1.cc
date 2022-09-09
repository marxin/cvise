template <class> class j {
public:
	void func();
	
	template <class c>
	void func2(c p);
};

template <class m> void j<m>::func() {
	return *this;
}

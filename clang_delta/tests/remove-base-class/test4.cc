template <class T> 
struct c {
  c(T) {}
};

struct i : c<double>, c<int> {
  template <class T>
  i() : c<double>(1.0), c<int>(10) {}
};

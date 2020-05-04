namespace NS1 {
  template <class T> struct Base {};
  template <class T> struct Derived: public Base<T> {
    typename Derived::template Base<double>* p1;
  };
}
template <class T> struct Base {};
template <class T> struct Derived: public Base<T> {
  typename Derived::template Base<double>* p1;
};

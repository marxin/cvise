namespace NS1 {
namespace NS2 {
  template<class T>
  T foo(T p1, T p2);

  template<class T>
  T operator+(T p1, T p2);
  int func();
}
}
namespace NS3 {
  struct S {};
  S s1, s2;
  using namespace NS1::NS2;
  int bar() {
    func();
    return 0;
  }
}

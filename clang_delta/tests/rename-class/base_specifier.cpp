namespace NS1 {
  template<class T> class Class1;
  template<class T> class Basic {};
  template<class T> class Class1: public Basic<T> {};
}
namespace NS2 {
  class Class1;
  class Basic {};
  class Class1: public Basic {};
}

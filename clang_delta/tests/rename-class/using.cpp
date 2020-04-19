template <class T> struct Base {
  typedef T value_type;
};

template <class T> struct Derived : Base<T> {
  using Base<T>::value_type;
  typename Base<T>::value_type get();
};

template<typename T> struct SomeClass {
  SomeClass() {}
  ~SomeClass() {}
};

template<typename T> struct MyTypeDef {
  typedef SomeClass<T> type;
};

template<typename T>
using MyType = SomeClass<T>;
MyType<int> mytype;

template <class T> using Ptr = T*;
Ptr<int> ip;

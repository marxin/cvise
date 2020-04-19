namespace NS1 {
  template<class T, class T2 = T> struct S1;
  template<class T> struct S2 {};
}

namespace NS2 {
  template<class T, class T2 = T, class T3 = void>
  struct S1 : NS1::S1<typename NS1::S2<T>::type, T2> {};
}

namespace NS1 {
  template<class T, class T2> struct S1 {};
}

namespace NS {
  template <typename T1>
  class AAA {};
}

template <typename T1>
class BBB: NS::AAA<T1> {};

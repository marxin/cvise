namespace NS1 {
  template<typename T> class AAA {};
}

class BBB : public NS1::AAA<bool> {};

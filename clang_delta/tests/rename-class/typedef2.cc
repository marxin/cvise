namespace NS {
  template<bool C> struct S1;
  typedef S1<false> S1_t;

  template<bool C> struct S1 {
    typedef S1 type;
  };
}

struct S2 : NS::S1_t {};

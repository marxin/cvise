template<typename T>
struct AAA {
  AAA& foo(AAA *) { return *this; }
};


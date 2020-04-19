template<typename T1, typename T2>
struct AAA {
  typedef T2 new_type;
};

template<typename T3>
struct BBB : public AAA<int, T3>::new_type { };

template <typename T, int N>
struct S1 {
  T value() const { return N; }
};

template <typename T>
struct S1 <T, 3> {
  T value() const { return 0; }
};


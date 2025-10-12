template <typename T>
struct A : T {
  using typename T::C;
  using E = typename C::D;
  using F = E;
};

struct B {
  struct C {
    using D = int;
  };
};

using G = A<B>::F;

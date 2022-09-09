// Check that h is not replaced by "(anonymous namespace)::k"

namespace {
struct k {
};
}

template <class h> struct G {
  using ac = h;
};

int main() {
  G<k> v;
}

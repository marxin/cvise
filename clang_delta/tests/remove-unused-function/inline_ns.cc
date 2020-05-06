namespace a {
  inline namespace b {
    using namespace a;
  }
  struct c;
  namespace {
    using a::c;
  }
}

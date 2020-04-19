template <int> struct a {};
template <typename> struct b : a<false> {};
template <template <typename> typename> struct c;
template <typename d> using e = typename d::f;
template <int> struct j;
template <typename g> using h = e<c<j<sizeof(g)>::template i>>;

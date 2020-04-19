template < class, class, class > class a {};
template < class i, class az, class ba, class bb, class bc >
int operator*(a< i, az, bb >, a< i, ba, bc >);
void bh() {
  a<int, int, int> bg;
  bg * bg;
}

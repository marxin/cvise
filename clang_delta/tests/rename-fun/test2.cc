// Check that rename-fun cannot rename anything within this test case
// Maybe in future rename-fun can also rename templates functions
template < class a, class = a > class b;
template < class a > void fn1(a &&);
template < class, class > struct b { void e(int &&); };
template < class a, class d > void b< a, d >::e(int &&g) { fn1(g); }
void fn3() {
  b< int > h;
  h.e(0);
}

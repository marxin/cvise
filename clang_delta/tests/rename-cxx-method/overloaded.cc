template < class> struct k  {
  template < class l > void operator=(int);
};
struct G { void p() { } };
template < class i>
template < class l>
k<i>::k() { operator=(1); }

template <typename T> struct S {template <typename T1> void foo();};
template<typename T> template<typename T1> void S<T>::foo() { }

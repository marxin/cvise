struct S {};
template<typename T>
S foo(T &, T &) = delete;

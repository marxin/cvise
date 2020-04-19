template<typename T>
class SomeClass1 {
public:
  SomeClass1() {}
  ~SomeClass1<T>() {}
};

template<typename T>
class SomeClass2 {
public:
  SomeClass2<T>() {}
  ~SomeClass2<T>() {}
};

template<typename T>
class SomeClass3 {
public:
  SomeClass3() {}
  ~SomeClass3() {}
};

template<typename T>
class SomeClass4 {
public:
  SomeClass4<T>() {}
  ~SomeClass4() {}
};


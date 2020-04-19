template<template<class> class BBB>
struct AAA {
  template <class T> struct CCC {
      static BBB<T> a;
  };
};

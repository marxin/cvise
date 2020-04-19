template<typename>
struct AAA {};

template<template <typename> class >
struct BBB {
  BBB() {}
};

BBB<AAA> b;

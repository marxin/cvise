struct AAA {};
template<typename T> class BBB {};
template<> class BBB<int> : public AAA {};

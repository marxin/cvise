class Moo {
public:
  static int foo() { return 10; }
  static int bar() { return 10; }
};

void quack(void) {
  if (Moo::foo())
    ;
}

struct S {
  int f1;
} a, b[1];

int foo()
{
  return a.f1 + b[0].f1;
}

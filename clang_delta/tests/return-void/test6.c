#define M(x) (x)
const void *test(void) {
  int *t = 0;
  return M(t);
}

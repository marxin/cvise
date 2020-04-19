#define LBRAC {
#define RBRAC }

void foo(void) {
   if (!0) LBRAC
     0;
   RBRAC
}

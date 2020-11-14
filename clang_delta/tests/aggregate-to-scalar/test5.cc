extern "C" {
  extern char *gnu_optarg;
}

char foo() {
 return gnu_optarg[0];
}

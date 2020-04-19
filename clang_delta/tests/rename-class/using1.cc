namespace NS {
  struct XYZ { static void foo(); };
  void XYZ::foo() {}
}

using NS::XYZ;
void bar(void) {
  NS::XYZ::foo();
}

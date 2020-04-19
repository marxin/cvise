## -*- mode: CMake -*-
##
## Copyright (c) 2012, 2013, 2014, 2015, 2016, 2017, 2018, 2019 The University of Utah
## All rights reserved.
##
## This file is distributed under the University of Illinois Open Source
## License.  See the file COPYING for details.

###############################################################################

cmake_minimum_required(VERSION 2.8.12)
project(clang_delta)

###############################################################################

# find_package(LLVM) is done by the topmost "CMakeLists.txt" file.
# find_package(Clang) is done by the topmost "CMakeLists.txt" file.

# Generate file "git_version.cpp".
#
configure_file("git_version.cpp.in" "git_version.cpp" @ONLY)

configure_file(
  "${clang_delta_SOURCE_DIR}/tests/test_clang_delta.py"
  "${clang_delta_BINARY_DIR}/tests/test_clang_delta.py"
  COPYONLY
)

configure_file(
  "${clang_delta_SOURCE_DIR}/tests/aggregate-to-scalar/cast.c"
  "${clang_delta_BINARY_DIR}/tests/aggregate-to-scalar/cast.c"
  COPYONLY
)

configure_file(
  "${clang_delta_SOURCE_DIR}/tests/aggregate-to-scalar/cast.output"
  "${clang_delta_BINARY_DIR}/tests/aggregate-to-scalar/cast.output"
  COPYONLY
)

configure_file(
  "${clang_delta_SOURCE_DIR}/tests/aggregate-to-scalar/test1.c"
  "${clang_delta_BINARY_DIR}/tests/aggregate-to-scalar/test1.c"
  COPYONLY
)

configure_file(
  "${clang_delta_SOURCE_DIR}/tests/aggregate-to-scalar/test1.output"
  "${clang_delta_BINARY_DIR}/tests/aggregate-to-scalar/test1.output"
  COPYONLY
)

configure_file(
  "${clang_delta_SOURCE_DIR}/tests/aggregate-to-scalar/test1.cc"
  "${clang_delta_BINARY_DIR}/tests/aggregate-to-scalar/test1.cc"
  COPYONLY
)

configure_file(
  "${clang_delta_SOURCE_DIR}/tests/aggregate-to-scalar/test1.output"
  "${clang_delta_BINARY_DIR}/tests/aggregate-to-scalar/test1.output"
  COPYONLY
)

configure_file(
  "${clang_delta_SOURCE_DIR}/tests/aggregate-to-scalar/test2.c"
  "${clang_delta_BINARY_DIR}/tests/aggregate-to-scalar/test2.c"
  COPYONLY
)

configure_file(
  "${clang_delta_SOURCE_DIR}/tests/aggregate-to-scalar/test2.output"
  "${clang_delta_BINARY_DIR}/tests/aggregate-to-scalar/test2.output"
  COPYONLY
)

configure_file(
  "${clang_delta_SOURCE_DIR}/tests/aggregate-to-scalar/test2.cc"
  "${clang_delta_BINARY_DIR}/tests/aggregate-to-scalar/test2.cc"
  COPYONLY
)

configure_file(
  "${clang_delta_SOURCE_DIR}/tests/aggregate-to-scalar/test2.output"
  "${clang_delta_BINARY_DIR}/tests/aggregate-to-scalar/test2.output"
  COPYONLY
)

configure_file(
  "${clang_delta_SOURCE_DIR}/tests/aggregate-to-scalar/test3.c"
  "${clang_delta_BINARY_DIR}/tests/aggregate-to-scalar/test3.c"
  COPYONLY
)

configure_file(
  "${clang_delta_SOURCE_DIR}/tests/aggregate-to-scalar/test3.output"
  "${clang_delta_BINARY_DIR}/tests/aggregate-to-scalar/test3.output"
  COPYONLY
)

configure_file(
  "${clang_delta_SOURCE_DIR}/tests/aggregate-to-scalar/test4.c"
  "${clang_delta_BINARY_DIR}/tests/aggregate-to-scalar/test4.c"
  COPYONLY
)

configure_file(
  "${clang_delta_SOURCE_DIR}/tests/aggregate-to-scalar/test4.output"
  "${clang_delta_BINARY_DIR}/tests/aggregate-to-scalar/test4.output"
  COPYONLY
)

configure_file(
  "${clang_delta_SOURCE_DIR}/tests/callexpr-to-value/macro1.c"
  "${clang_delta_BINARY_DIR}/tests/callexpr-to-value/macro1.c"
  COPYONLY
)

configure_file(
  "${clang_delta_SOURCE_DIR}/tests/callexpr-to-value/macro1.output"
  "${clang_delta_BINARY_DIR}/tests/callexpr-to-value/macro1.output"
  COPYONLY
)

configure_file(
  "${clang_delta_SOURCE_DIR}/tests/callexpr-to-value/macro2.c"
  "${clang_delta_BINARY_DIR}/tests/callexpr-to-value/macro2.c"
  COPYONLY
)

configure_file(
  "${clang_delta_SOURCE_DIR}/tests/callexpr-to-value/macro2.output"
  "${clang_delta_BINARY_DIR}/tests/callexpr-to-value/macro2.output"
  COPYONLY
)

configure_file(
  "${clang_delta_SOURCE_DIR}/tests/callexpr-to-value/test1.c"
  "${clang_delta_BINARY_DIR}/tests/callexpr-to-value/test1.c"
  COPYONLY
)

configure_file(
  "${clang_delta_SOURCE_DIR}/tests/callexpr-to-value/test1.output"
  "${clang_delta_BINARY_DIR}/tests/callexpr-to-value/test1.output"
  COPYONLY
)

configure_file(
  "${clang_delta_SOURCE_DIR}/tests/callexpr-to-value/test2.c"
  "${clang_delta_BINARY_DIR}/tests/callexpr-to-value/test2.c"
  COPYONLY
)

configure_file(
  "${clang_delta_SOURCE_DIR}/tests/callexpr-to-value/test2.output"
  "${clang_delta_BINARY_DIR}/tests/callexpr-to-value/test2.output"
  COPYONLY
)

configure_file(
  "${clang_delta_SOURCE_DIR}/tests/copy-propagation/copy1.cpp"
  "${clang_delta_BINARY_DIR}/tests/copy-propagation/copy1.cpp"
  COPYONLY
)

configure_file(
  "${clang_delta_SOURCE_DIR}/tests/copy-propagation/copy1.output"
  "${clang_delta_BINARY_DIR}/tests/copy-propagation/copy1.output"
  COPYONLY
)

configure_file(
  "${clang_delta_SOURCE_DIR}/tests/copy-propagation/copy2.cpp"
  "${clang_delta_BINARY_DIR}/tests/copy-propagation/copy2.cpp"
  COPYONLY
)

configure_file(
  "${clang_delta_SOURCE_DIR}/tests/copy-propagation/copy2.output"
  "${clang_delta_BINARY_DIR}/tests/copy-propagation/copy2.output"
  COPYONLY
)

configure_file(
  "${clang_delta_SOURCE_DIR}/tests/empty-struct-to-int/empty-struct.cpp"
  "${clang_delta_BINARY_DIR}/tests/empty-struct-to-int/empty-struct.cpp"
  COPYONLY
)

configure_file(
  "${clang_delta_SOURCE_DIR}/tests/empty-struct-to-int/empty-struct.output"
  "${clang_delta_BINARY_DIR}/tests/empty-struct-to-int/empty-struct.output"
  COPYONLY
)

configure_file(
  "${clang_delta_SOURCE_DIR}/tests/empty-struct-to-int/empty-struct2.cpp"
  "${clang_delta_BINARY_DIR}/tests/empty-struct-to-int/empty-struct2.cpp"
  COPYONLY
)

configure_file(
  "${clang_delta_SOURCE_DIR}/tests/empty-struct-to-int/empty-struct2.output"
  "${clang_delta_BINARY_DIR}/tests/empty-struct-to-int/empty-struct2.output"
  COPYONLY
)

configure_file(
  "${clang_delta_SOURCE_DIR}/tests/empty-struct-to-int/empty-struct3.cpp"
  "${clang_delta_BINARY_DIR}/tests/empty-struct-to-int/empty-struct3.cpp"
  COPYONLY
)

configure_file(
  "${clang_delta_SOURCE_DIR}/tests/empty-struct-to-int/empty-struct3.output"
  "${clang_delta_BINARY_DIR}/tests/empty-struct-to-int/empty-struct3.output"
  COPYONLY
)

configure_file(
  "${clang_delta_SOURCE_DIR}/tests/empty-struct-to-int/empty-struct4.cpp"
  "${clang_delta_BINARY_DIR}/tests/empty-struct-to-int/empty-struct4.cpp"
  COPYONLY
)

configure_file(
  "${clang_delta_SOURCE_DIR}/tests/empty-struct-to-int/empty-struct4.output"
  "${clang_delta_BINARY_DIR}/tests/empty-struct-to-int/empty-struct4.output"
  COPYONLY
)

configure_file(
  "${clang_delta_SOURCE_DIR}/tests/empty-struct-to-int/empty-struct5.cpp"
  "${clang_delta_BINARY_DIR}/tests/empty-struct-to-int/empty-struct5.cpp"
  COPYONLY
)

configure_file(
  "${clang_delta_SOURCE_DIR}/tests/empty-struct-to-int/empty-struct5.output"
  "${clang_delta_BINARY_DIR}/tests/empty-struct-to-int/empty-struct5.output"
  COPYONLY
)

configure_file(
  "${clang_delta_SOURCE_DIR}/tests/empty-struct-to-int/empty-struct6.c"
  "${clang_delta_BINARY_DIR}/tests/empty-struct-to-int/empty-struct6.c"
  COPYONLY
)

configure_file(
  "${clang_delta_SOURCE_DIR}/tests/empty-struct-to-int/empty-struct6.output"
  "${clang_delta_BINARY_DIR}/tests/empty-struct-to-int/empty-struct6.output"
  COPYONLY
)

configure_file(
  "${clang_delta_SOURCE_DIR}/tests/empty-struct-to-int/empty-struct7.c"
  "${clang_delta_BINARY_DIR}/tests/empty-struct-to-int/empty-struct7.c"
  COPYONLY
)

configure_file(
  "${clang_delta_SOURCE_DIR}/tests/empty-struct-to-int/empty-struct7.output"
  "${clang_delta_BINARY_DIR}/tests/empty-struct-to-int/empty-struct7.output"
  COPYONLY
)

configure_file(
  "${clang_delta_SOURCE_DIR}/tests/empty-struct-to-int/struct_int.c"
  "${clang_delta_BINARY_DIR}/tests/empty-struct-to-int/struct_int.c"
  COPYONLY
)

configure_file(
  "${clang_delta_SOURCE_DIR}/tests/empty-struct-to-int/struct_int.output"
  "${clang_delta_BINARY_DIR}/tests/empty-struct-to-int/struct_int.output"
  COPYONLY
)

configure_file(
  "${clang_delta_SOURCE_DIR}/tests/empty-struct-to-int/test1.cc"
  "${clang_delta_BINARY_DIR}/tests/empty-struct-to-int/test1.cc"
  COPYONLY
)

configure_file(
  "${clang_delta_SOURCE_DIR}/tests/empty-struct-to-int/test1.output"
  "${clang_delta_BINARY_DIR}/tests/empty-struct-to-int/test1.output"
  COPYONLY
)

configure_file(
  "${clang_delta_SOURCE_DIR}/tests/empty-struct-to-int/test2.cc"
  "${clang_delta_BINARY_DIR}/tests/empty-struct-to-int/test2.cc"
  COPYONLY
)

configure_file(
  "${clang_delta_SOURCE_DIR}/tests/empty-struct-to-int/test2.output"
  "${clang_delta_BINARY_DIR}/tests/empty-struct-to-int/test2.output"
  COPYONLY
)

configure_file(
  "${clang_delta_SOURCE_DIR}/tests/empty-struct-to-int/test3.c"
  "${clang_delta_BINARY_DIR}/tests/empty-struct-to-int/test3.c"
  COPYONLY
)

configure_file(
  "${clang_delta_SOURCE_DIR}/tests/empty-struct-to-int/test3.output"
  "${clang_delta_BINARY_DIR}/tests/empty-struct-to-int/test3.output"
  COPYONLY
)

configure_file(
  "${clang_delta_SOURCE_DIR}/tests/local-to-global/macro.c"
  "${clang_delta_BINARY_DIR}/tests/local-to-global/macro.c"
  COPYONLY
)

configure_file(
  "${clang_delta_SOURCE_DIR}/tests/local-to-global/macro.output"
  "${clang_delta_BINARY_DIR}/tests/local-to-global/macro.output"
  COPYONLY
)

configure_file(
  "${clang_delta_SOURCE_DIR}/tests/local-to-global/unnamed_1.c"
  "${clang_delta_BINARY_DIR}/tests/local-to-global/unnamed_1.c"
  COPYONLY
)

configure_file(
  "${clang_delta_SOURCE_DIR}/tests/local-to-global/unnamed_1.output"
  "${clang_delta_BINARY_DIR}/tests/local-to-global/unnamed_1.output"
  COPYONLY
)

configure_file(
  "${clang_delta_SOURCE_DIR}/tests/local-to-global/unnamed_2.c"
  "${clang_delta_BINARY_DIR}/tests/local-to-global/unnamed_2.c"
  COPYONLY
)

configure_file(
  "${clang_delta_SOURCE_DIR}/tests/local-to-global/unnamed_2.output"
  "${clang_delta_BINARY_DIR}/tests/local-to-global/unnamed_2.output"
  COPYONLY
)

configure_file(
  "${clang_delta_SOURCE_DIR}/tests/local-to-global/unnamed_3.c"
  "${clang_delta_BINARY_DIR}/tests/local-to-global/unnamed_3.c"
  COPYONLY
)

configure_file(
  "${clang_delta_SOURCE_DIR}/tests/local-to-global/unnamed_3.output"
  "${clang_delta_BINARY_DIR}/tests/local-to-global/unnamed_3.output"
  COPYONLY
)

configure_file(
  "${clang_delta_SOURCE_DIR}/tests/param-to-global/macro.c"
  "${clang_delta_BINARY_DIR}/tests/param-to-global/macro.c"
  COPYONLY
)

configure_file(
  "${clang_delta_SOURCE_DIR}/tests/param-to-global/macro.output"
  "${clang_delta_BINARY_DIR}/tests/param-to-global/macro.output"
  COPYONLY
)

configure_file(
  "${clang_delta_SOURCE_DIR}/tests/reduce-array-dim/non-type-temp-arg.cpp"
  "${clang_delta_BINARY_DIR}/tests/reduce-array-dim/non-type-temp-arg.cpp"
  COPYONLY
)

configure_file(
  "${clang_delta_SOURCE_DIR}/tests/reduce-array-dim/non-type-temp-arg.output"
  "${clang_delta_BINARY_DIR}/tests/reduce-array-dim/non-type-temp-arg.output"
  COPYONLY
)

configure_file(
  "${clang_delta_SOURCE_DIR}/tests/reduce-pointer-level/scalar-init-expr.cpp"
  "${clang_delta_BINARY_DIR}/tests/reduce-pointer-level/scalar-init-expr.cpp"
  COPYONLY
)

configure_file(
  "${clang_delta_SOURCE_DIR}/tests/reduce-pointer-level/scalar-init-expr.output"
  "${clang_delta_BINARY_DIR}/tests/reduce-pointer-level/scalar-init-expr.output"
  COPYONLY
)

configure_file(
  "${clang_delta_SOURCE_DIR}/tests/remove-enum-member-value/builtin_macro.c"
  "${clang_delta_BINARY_DIR}/tests/remove-enum-member-value/builtin_macro.c"
  COPYONLY
)

configure_file(
  "${clang_delta_SOURCE_DIR}/tests/remove-enum-member-value/builtin_macro.output"
  "${clang_delta_BINARY_DIR}/tests/remove-enum-member-value/builtin_macro.output"
  COPYONLY
)

configure_file(
  "${clang_delta_SOURCE_DIR}/tests/remove-nested-function/remove_nested_func1.cc"
  "${clang_delta_BINARY_DIR}/tests/remove-nested-function/remove_nested_func1.cc"
  COPYONLY
)

configure_file(
  "${clang_delta_SOURCE_DIR}/tests/remove-nested-function/remove_nested_func1.output"
  "${clang_delta_BINARY_DIR}/tests/remove-nested-function/remove_nested_func1.output"
  COPYONLY
)

configure_file(
  "${clang_delta_SOURCE_DIR}/tests/remove-unused-field/designated1.c"
  "${clang_delta_BINARY_DIR}/tests/remove-unused-field/designated1.c"
  COPYONLY
)

configure_file(
  "${clang_delta_SOURCE_DIR}/tests/remove-unused-field/designated1.output"
  "${clang_delta_BINARY_DIR}/tests/remove-unused-field/designated1.output"
  COPYONLY
)

configure_file(
  "${clang_delta_SOURCE_DIR}/tests/remove-unused-field/designated2.c"
  "${clang_delta_BINARY_DIR}/tests/remove-unused-field/designated2.c"
  COPYONLY
)

configure_file(
  "${clang_delta_SOURCE_DIR}/tests/remove-unused-field/designated2.output"
  "${clang_delta_BINARY_DIR}/tests/remove-unused-field/designated2.output"
  COPYONLY
)

configure_file(
  "${clang_delta_SOURCE_DIR}/tests/remove-unused-field/designated3.c"
  "${clang_delta_BINARY_DIR}/tests/remove-unused-field/designated3.c"
  COPYONLY
)

configure_file(
  "${clang_delta_SOURCE_DIR}/tests/remove-unused-field/designated3.output"
  "${clang_delta_BINARY_DIR}/tests/remove-unused-field/designated3.output"
  COPYONLY
)

configure_file(
  "${clang_delta_SOURCE_DIR}/tests/remove-unused-field/designated4.c"
  "${clang_delta_BINARY_DIR}/tests/remove-unused-field/designated4.c"
  COPYONLY
)

configure_file(
  "${clang_delta_SOURCE_DIR}/tests/remove-unused-field/designated4.output"
  "${clang_delta_BINARY_DIR}/tests/remove-unused-field/designated4.output"
  COPYONLY
)

configure_file(
  "${clang_delta_SOURCE_DIR}/tests/remove-unused-field/designated5.c"
  "${clang_delta_BINARY_DIR}/tests/remove-unused-field/designated5.c"
  COPYONLY
)

configure_file(
  "${clang_delta_SOURCE_DIR}/tests/remove-unused-field/designated5.output"
  "${clang_delta_BINARY_DIR}/tests/remove-unused-field/designated5.output"
  COPYONLY
)

configure_file(
  "${clang_delta_SOURCE_DIR}/tests/remove-unused-field/unused_field1.c"
  "${clang_delta_BINARY_DIR}/tests/remove-unused-field/unused_field1.c"
  COPYONLY
)

configure_file(
  "${clang_delta_SOURCE_DIR}/tests/remove-unused-field/unused_field1.output"
  "${clang_delta_BINARY_DIR}/tests/remove-unused-field/unused_field1.output"
  COPYONLY
)

configure_file(
  "${clang_delta_SOURCE_DIR}/tests/remove-unused-field/unused_field2.c"
  "${clang_delta_BINARY_DIR}/tests/remove-unused-field/unused_field2.c"
  COPYONLY
)

configure_file(
  "${clang_delta_SOURCE_DIR}/tests/remove-unused-field/unused_field2.output"
  "${clang_delta_BINARY_DIR}/tests/remove-unused-field/unused_field2.output"
  COPYONLY
)

configure_file(
  "${clang_delta_SOURCE_DIR}/tests/remove-unused-field/unused_field3.cpp"
  "${clang_delta_BINARY_DIR}/tests/remove-unused-field/unused_field3.cpp"
  COPYONLY
)

configure_file(
  "${clang_delta_SOURCE_DIR}/tests/remove-unused-field/unused_field3.output"
  "${clang_delta_BINARY_DIR}/tests/remove-unused-field/unused_field3.output"
  COPYONLY
)

configure_file(
  "${clang_delta_SOURCE_DIR}/tests/remove-unused-function/class.cc"
  "${clang_delta_BINARY_DIR}/tests/remove-unused-function/class.cc"
  COPYONLY
)

configure_file(
  "${clang_delta_SOURCE_DIR}/tests/remove-unused-function/class.output"
  "${clang_delta_BINARY_DIR}/tests/remove-unused-function/class.output"
  COPYONLY
)

configure_file(
  "${clang_delta_SOURCE_DIR}/tests/remove-unused-function/macro1.cc"
  "${clang_delta_BINARY_DIR}/tests/remove-unused-function/macro1.cc"
  COPYONLY
)

configure_file(
  "${clang_delta_SOURCE_DIR}/tests/remove-unused-function/macro1.output"
  "${clang_delta_BINARY_DIR}/tests/remove-unused-function/macro1.output"
  COPYONLY
)

configure_file(
  "${clang_delta_SOURCE_DIR}/tests/remove-unused-function/macro2.cc"
  "${clang_delta_BINARY_DIR}/tests/remove-unused-function/macro2.cc"
  COPYONLY
)

configure_file(
  "${clang_delta_SOURCE_DIR}/tests/remove-unused-function/macro2.output"
  "${clang_delta_BINARY_DIR}/tests/remove-unused-function/macro2.output"
  COPYONLY
)

configure_file(
  "${clang_delta_SOURCE_DIR}/tests/remove-unused-function/macro3.cc"
  "${clang_delta_BINARY_DIR}/tests/remove-unused-function/macro3.cc"
  COPYONLY
)

configure_file(
  "${clang_delta_SOURCE_DIR}/tests/remove-unused-function/macro3.output"
  "${clang_delta_BINARY_DIR}/tests/remove-unused-function/macro3.output"
  COPYONLY
)

configure_file(
  "${clang_delta_SOURCE_DIR}/tests/remove-unused-function/template1.cc"
  "${clang_delta_BINARY_DIR}/tests/remove-unused-function/template1.cc"
  COPYONLY
)

configure_file(
  "${clang_delta_SOURCE_DIR}/tests/remove-unused-function/template1.output"
  "${clang_delta_BINARY_DIR}/tests/remove-unused-function/template1.output"
  COPYONLY
)

configure_file(
  "${clang_delta_SOURCE_DIR}/tests/remove-unused-function/template2.cc"
  "${clang_delta_BINARY_DIR}/tests/remove-unused-function/template2.cc"
  COPYONLY
)

configure_file(
  "${clang_delta_SOURCE_DIR}/tests/remove-unused-function/template2.output"
  "${clang_delta_BINARY_DIR}/tests/remove-unused-function/template2.output"
  COPYONLY
)

configure_file(
  "${clang_delta_SOURCE_DIR}/tests/remove-unused-function/unused-funcs.cc"
  "${clang_delta_BINARY_DIR}/tests/remove-unused-function/unused-funcs.cc"
  COPYONLY
)

configure_file(
  "${clang_delta_SOURCE_DIR}/tests/remove-unused-function/unused-funcs.output"
  "${clang_delta_BINARY_DIR}/tests/remove-unused-function/unused-funcs.output"
  COPYONLY
)

configure_file(
  "${clang_delta_SOURCE_DIR}/tests/remove-unused-var/struct1.c"
  "${clang_delta_BINARY_DIR}/tests/remove-unused-var/struct1.c"
  COPYONLY
)

configure_file(
  "${clang_delta_SOURCE_DIR}/tests/remove-unused-var/struct1.output"
  "${clang_delta_BINARY_DIR}/tests/remove-unused-var/struct1.output"
  COPYONLY
)

configure_file(
  "${clang_delta_SOURCE_DIR}/tests/remove-unused-var/struct2.c"
  "${clang_delta_BINARY_DIR}/tests/remove-unused-var/struct2.c"
  COPYONLY
)

configure_file(
  "${clang_delta_SOURCE_DIR}/tests/remove-unused-var/struct2.output"
  "${clang_delta_BINARY_DIR}/tests/remove-unused-var/struct2.output"
  COPYONLY
)

configure_file(
  "${clang_delta_SOURCE_DIR}/tests/remove-unused-var/unused_var.cpp"
  "${clang_delta_BINARY_DIR}/tests/remove-unused-var/unused_var.cpp"
  COPYONLY
)

configure_file(
  "${clang_delta_SOURCE_DIR}/tests/remove-unused-var/unused_var.output"
  "${clang_delta_BINARY_DIR}/tests/remove-unused-var/unused_var.output"
  COPYONLY
)

configure_file(
  "${clang_delta_SOURCE_DIR}/tests/rename-class/base_specifier.cpp"
  "${clang_delta_BINARY_DIR}/tests/rename-class/base_specifier.cpp"
  COPYONLY
)

configure_file(
  "${clang_delta_SOURCE_DIR}/tests/rename-class/base_specifier.output"
  "${clang_delta_BINARY_DIR}/tests/rename-class/base_specifier.output"
  COPYONLY
)

configure_file(
  "${clang_delta_SOURCE_DIR}/tests/rename-class/bool.cc"
  "${clang_delta_BINARY_DIR}/tests/rename-class/bool.cc"
  COPYONLY
)

configure_file(
  "${clang_delta_SOURCE_DIR}/tests/rename-class/bool.output"
  "${clang_delta_BINARY_DIR}/tests/rename-class/bool.output"
  COPYONLY
)

configure_file(
  "${clang_delta_SOURCE_DIR}/tests/rename-class/class_template.cc"
  "${clang_delta_BINARY_DIR}/tests/rename-class/class_template.cc"
  COPYONLY
)

configure_file(
  "${clang_delta_SOURCE_DIR}/tests/rename-class/class_template.output"
  "${clang_delta_BINARY_DIR}/tests/rename-class/class_template.output"
  COPYONLY
)

configure_file(
  "${clang_delta_SOURCE_DIR}/tests/rename-class/class_template2.cc"
  "${clang_delta_BINARY_DIR}/tests/rename-class/class_template2.cc"
  COPYONLY
)

configure_file(
  "${clang_delta_SOURCE_DIR}/tests/rename-class/class_template2.output"
  "${clang_delta_BINARY_DIR}/tests/rename-class/class_template2.output"
  COPYONLY
)

configure_file(
  "${clang_delta_SOURCE_DIR}/tests/rename-class/dependent.cpp"
  "${clang_delta_BINARY_DIR}/tests/rename-class/dependent.cpp"
  COPYONLY
)

configure_file(
  "${clang_delta_SOURCE_DIR}/tests/rename-class/dependent.output"
  "${clang_delta_BINARY_DIR}/tests/rename-class/dependent.output"
  COPYONLY
)

configure_file(
  "${clang_delta_SOURCE_DIR}/tests/rename-class/dependent_name.cpp"
  "${clang_delta_BINARY_DIR}/tests/rename-class/dependent_name.cpp"
  COPYONLY
)

configure_file(
  "${clang_delta_SOURCE_DIR}/tests/rename-class/dependent_name.output"
  "${clang_delta_BINARY_DIR}/tests/rename-class/dependent_name.output"
  COPYONLY
)

configure_file(
  "${clang_delta_SOURCE_DIR}/tests/rename-class/derive.cc"
  "${clang_delta_BINARY_DIR}/tests/rename-class/derive.cc"
  COPYONLY
)

configure_file(
  "${clang_delta_SOURCE_DIR}/tests/rename-class/derive.output"
  "${clang_delta_BINARY_DIR}/tests/rename-class/derive.output"
  COPYONLY
)

configure_file(
  "${clang_delta_SOURCE_DIR}/tests/rename-class/dtor.cc"
  "${clang_delta_BINARY_DIR}/tests/rename-class/dtor.cc"
  COPYONLY
)

configure_file(
  "${clang_delta_SOURCE_DIR}/tests/rename-class/dtor.output"
  "${clang_delta_BINARY_DIR}/tests/rename-class/dtor.output"
  COPYONLY
)

configure_file(
  "${clang_delta_SOURCE_DIR}/tests/rename-class/dtor1.cc"
  "${clang_delta_BINARY_DIR}/tests/rename-class/dtor1.cc"
  COPYONLY
)

configure_file(
  "${clang_delta_SOURCE_DIR}/tests/rename-class/dtor1.output"
  "${clang_delta_BINARY_DIR}/tests/rename-class/dtor1.output"
  COPYONLY
)

configure_file(
  "${clang_delta_SOURCE_DIR}/tests/rename-class/elaborated_type1.cpp"
  "${clang_delta_BINARY_DIR}/tests/rename-class/elaborated_type1.cpp"
  COPYONLY
)

configure_file(
  "${clang_delta_SOURCE_DIR}/tests/rename-class/elaborated_type1.output"
  "${clang_delta_BINARY_DIR}/tests/rename-class/elaborated_type1.output"
  COPYONLY
)

configure_file(
  "${clang_delta_SOURCE_DIR}/tests/rename-class/elaborated_type2.cpp"
  "${clang_delta_BINARY_DIR}/tests/rename-class/elaborated_type2.cpp"
  COPYONLY
)

configure_file(
  "${clang_delta_SOURCE_DIR}/tests/rename-class/elaborated_type2.output"
  "${clang_delta_BINARY_DIR}/tests/rename-class/elaborated_type2.output"
  COPYONLY
)

configure_file(
  "${clang_delta_SOURCE_DIR}/tests/rename-class/explicit_specialization.cpp"
  "${clang_delta_BINARY_DIR}/tests/rename-class/explicit_specialization.cpp"
  COPYONLY
)

configure_file(
  "${clang_delta_SOURCE_DIR}/tests/rename-class/explicit_specialization.output"
  "${clang_delta_BINARY_DIR}/tests/rename-class/explicit_specialization.output"
  COPYONLY
)

configure_file(
  "${clang_delta_SOURCE_DIR}/tests/rename-class/forward_decl.cc"
  "${clang_delta_BINARY_DIR}/tests/rename-class/forward_decl.cc"
  COPYONLY
)

configure_file(
  "${clang_delta_SOURCE_DIR}/tests/rename-class/forward_decl.output"
  "${clang_delta_BINARY_DIR}/tests/rename-class/forward_decl.output"
  COPYONLY
)

configure_file(
  "${clang_delta_SOURCE_DIR}/tests/rename-class/injected_name.cpp"
  "${clang_delta_BINARY_DIR}/tests/rename-class/injected_name.cpp"
  COPYONLY
)

configure_file(
  "${clang_delta_SOURCE_DIR}/tests/rename-class/injected_name.output"
  "${clang_delta_BINARY_DIR}/tests/rename-class/injected_name.output"
  COPYONLY
)

configure_file(
  "${clang_delta_SOURCE_DIR}/tests/rename-class/instantiation.cpp"
  "${clang_delta_BINARY_DIR}/tests/rename-class/instantiation.cpp"
  COPYONLY
)

configure_file(
  "${clang_delta_SOURCE_DIR}/tests/rename-class/instantiation.output"
  "${clang_delta_BINARY_DIR}/tests/rename-class/instantiation.output"
  COPYONLY
)

configure_file(
  "${clang_delta_SOURCE_DIR}/tests/rename-class/parm.cpp"
  "${clang_delta_BINARY_DIR}/tests/rename-class/parm.cpp"
  COPYONLY
)

configure_file(
  "${clang_delta_SOURCE_DIR}/tests/rename-class/parm.output"
  "${clang_delta_BINARY_DIR}/tests/rename-class/parm.output"
  COPYONLY
)

configure_file(
  "${clang_delta_SOURCE_DIR}/tests/rename-class/partial_specialization.cpp"
  "${clang_delta_BINARY_DIR}/tests/rename-class/partial_specialization.cpp"
  COPYONLY
)

configure_file(
  "${clang_delta_SOURCE_DIR}/tests/rename-class/partial_specialization.output"
  "${clang_delta_BINARY_DIR}/tests/rename-class/partial_specialization.output"
  COPYONLY
)

configure_file(
  "${clang_delta_SOURCE_DIR}/tests/rename-class/rename-class1.cpp"
  "${clang_delta_BINARY_DIR}/tests/rename-class/rename-class1.cpp"
  COPYONLY
)

configure_file(
  "${clang_delta_SOURCE_DIR}/tests/rename-class/rename-class1.output"
  "${clang_delta_BINARY_DIR}/tests/rename-class/rename-class1.output"
  COPYONLY
)

configure_file(
  "${clang_delta_SOURCE_DIR}/tests/rename-class/rename-class2.cpp"
  "${clang_delta_BINARY_DIR}/tests/rename-class/rename-class2.cpp"
  COPYONLY
)

configure_file(
  "${clang_delta_SOURCE_DIR}/tests/rename-class/rename-class2.output"
  "${clang_delta_BINARY_DIR}/tests/rename-class/rename-class2.output"
  COPYONLY
)

configure_file(
  "${clang_delta_SOURCE_DIR}/tests/rename-class/specialization.cpp"
  "${clang_delta_BINARY_DIR}/tests/rename-class/specialization.cpp"
  COPYONLY
)

configure_file(
  "${clang_delta_SOURCE_DIR}/tests/rename-class/specialization.output"
  "${clang_delta_BINARY_DIR}/tests/rename-class/specialization.output"
  COPYONLY
)

configure_file(
  "${clang_delta_SOURCE_DIR}/tests/rename-class/static_member.cc"
  "${clang_delta_BINARY_DIR}/tests/rename-class/static_member.cc"
  COPYONLY
)

configure_file(
  "${clang_delta_SOURCE_DIR}/tests/rename-class/static_member.output"
  "${clang_delta_BINARY_DIR}/tests/rename-class/static_member.output"
  COPYONLY
)

configure_file(
  "${clang_delta_SOURCE_DIR}/tests/rename-class/template_class_1.cpp"
  "${clang_delta_BINARY_DIR}/tests/rename-class/template_class_1.cpp"
  COPYONLY
)

configure_file(
  "${clang_delta_SOURCE_DIR}/tests/rename-class/template_class_1.output"
  "${clang_delta_BINARY_DIR}/tests/rename-class/template_class_1.output"
  COPYONLY
)

configure_file(
  "${clang_delta_SOURCE_DIR}/tests/rename-class/template_parm.cpp"
  "${clang_delta_BINARY_DIR}/tests/rename-class/template_parm.cpp"
  COPYONLY
)

configure_file(
  "${clang_delta_SOURCE_DIR}/tests/rename-class/template_parm.output"
  "${clang_delta_BINARY_DIR}/tests/rename-class/template_parm.output"
  COPYONLY
)

configure_file(
  "${clang_delta_SOURCE_DIR}/tests/rename-class/template_template.cpp"
  "${clang_delta_BINARY_DIR}/tests/rename-class/template_template.cpp"
  COPYONLY
)

configure_file(
  "${clang_delta_SOURCE_DIR}/tests/rename-class/template_template.output"
  "${clang_delta_BINARY_DIR}/tests/rename-class/template_template.output"
  COPYONLY
)

configure_file(
  "${clang_delta_SOURCE_DIR}/tests/rename-class/template_template_parm.cpp"
  "${clang_delta_BINARY_DIR}/tests/rename-class/template_template_parm.cpp"
  COPYONLY
)

configure_file(
  "${clang_delta_SOURCE_DIR}/tests/rename-class/template_template_parm.output"
  "${clang_delta_BINARY_DIR}/tests/rename-class/template_template_parm.output"
  COPYONLY
)

configure_file(
  "${clang_delta_SOURCE_DIR}/tests/rename-class/typedef.cpp"
  "${clang_delta_BINARY_DIR}/tests/rename-class/typedef.cpp"
  COPYONLY
)

configure_file(
  "${clang_delta_SOURCE_DIR}/tests/rename-class/typedef.output"
  "${clang_delta_BINARY_DIR}/tests/rename-class/typedef.output"
  COPYONLY
)

configure_file(
  "${clang_delta_SOURCE_DIR}/tests/rename-class/typedef2.cc"
  "${clang_delta_BINARY_DIR}/tests/rename-class/typedef2.cc"
  COPYONLY
)

configure_file(
  "${clang_delta_SOURCE_DIR}/tests/rename-class/typedef2.output"
  "${clang_delta_BINARY_DIR}/tests/rename-class/typedef2.output"
  COPYONLY
)

configure_file(
  "${clang_delta_SOURCE_DIR}/tests/rename-class/using.cpp"
  "${clang_delta_BINARY_DIR}/tests/rename-class/using.cpp"
  COPYONLY
)

configure_file(
  "${clang_delta_SOURCE_DIR}/tests/rename-class/using.output"
  "${clang_delta_BINARY_DIR}/tests/rename-class/using.output"
  COPYONLY
)

configure_file(
  "${clang_delta_SOURCE_DIR}/tests/rename-class/using1.cc"
  "${clang_delta_BINARY_DIR}/tests/rename-class/using1.cc"
  COPYONLY
)

configure_file(
  "${clang_delta_SOURCE_DIR}/tests/rename-class/using1.output"
  "${clang_delta_BINARY_DIR}/tests/rename-class/using1.output"
  COPYONLY
)

configure_file(
  "${clang_delta_SOURCE_DIR}/tests/rename-cxx-method/overloaded.cc"
  "${clang_delta_BINARY_DIR}/tests/rename-cxx-method/overloaded.cc"
  COPYONLY
)

configure_file(
  "${clang_delta_SOURCE_DIR}/tests/rename-cxx-method/overloaded.output"
  "${clang_delta_BINARY_DIR}/tests/rename-cxx-method/overloaded.output"
  COPYONLY
)

configure_file(
  "${clang_delta_SOURCE_DIR}/tests/rename-cxx-method/test1.cc"
  "${clang_delta_BINARY_DIR}/tests/rename-cxx-method/test1.cc"
  COPYONLY
)

configure_file(
  "${clang_delta_SOURCE_DIR}/tests/rename-cxx-method/test1.output"
  "${clang_delta_BINARY_DIR}/tests/rename-cxx-method/test1.output"
  COPYONLY
)

configure_file(
  "${clang_delta_SOURCE_DIR}/tests/rename-cxx-method/test2.cc"
  "${clang_delta_BINARY_DIR}/tests/rename-cxx-method/test2.cc"
  COPYONLY
)

configure_file(
  "${clang_delta_SOURCE_DIR}/tests/rename-cxx-method/test2.output"
  "${clang_delta_BINARY_DIR}/tests/rename-cxx-method/test2.output"
  COPYONLY
)

configure_file(
  "${clang_delta_SOURCE_DIR}/tests/rename-cxx-method/test3.cc"
  "${clang_delta_BINARY_DIR}/tests/rename-cxx-method/test3.cc"
  COPYONLY
)

configure_file(
  "${clang_delta_SOURCE_DIR}/tests/rename-cxx-method/test3.output"
  "${clang_delta_BINARY_DIR}/tests/rename-cxx-method/test3.output"
  COPYONLY
)

configure_file(
  "${clang_delta_SOURCE_DIR}/tests/rename-fun/overloaded.cc"
  "${clang_delta_BINARY_DIR}/tests/rename-fun/overloaded.cc"
  COPYONLY
)

configure_file(
  "${clang_delta_SOURCE_DIR}/tests/rename-fun/overloaded.output"
  "${clang_delta_BINARY_DIR}/tests/rename-fun/overloaded.output"
  COPYONLY
)

configure_file(
  "${clang_delta_SOURCE_DIR}/tests/rename-fun/test1.c"
  "${clang_delta_BINARY_DIR}/tests/rename-fun/test1.c"
  COPYONLY
)

configure_file(
  "${clang_delta_SOURCE_DIR}/tests/rename-fun/test1.output"
  "${clang_delta_BINARY_DIR}/tests/rename-fun/test1.output"
  COPYONLY
)

configure_file(
  "${clang_delta_SOURCE_DIR}/tests/rename-fun/multi.c"
  "${clang_delta_BINARY_DIR}/tests/rename-fun/multi.c"
  COPYONLY
)

configure_file(
  "${clang_delta_SOURCE_DIR}/tests/rename-fun/multi.output"
  "${clang_delta_BINARY_DIR}/tests/rename-fun/multi.output"
  COPYONLY
)

configure_file(
  "${clang_delta_SOURCE_DIR}/tests/rename-param/invalid.c"
  "${clang_delta_BINARY_DIR}/tests/rename-param/invalid.c"
  COPYONLY
)

configure_file(
  "${clang_delta_SOURCE_DIR}/tests/rename-param/invalid.output"
  "${clang_delta_BINARY_DIR}/tests/rename-param/invalid.output"
  COPYONLY
)

configure_file(
  "${clang_delta_SOURCE_DIR}/tests/rename-var/rename-var.c"
  "${clang_delta_BINARY_DIR}/tests/rename-var/rename-var.c"
  COPYONLY
)

configure_file(
  "${clang_delta_SOURCE_DIR}/tests/rename-var/rename-var.output"
  "${clang_delta_BINARY_DIR}/tests/rename-var/rename-var.output"
  COPYONLY
)

configure_file(
  "${clang_delta_SOURCE_DIR}/tests/replace-derived-class/replace-derived1.cpp"
  "${clang_delta_BINARY_DIR}/tests/replace-derived-class/replace-derived1.cpp"
  COPYONLY
)

configure_file(
  "${clang_delta_SOURCE_DIR}/tests/replace-derived-class/replace-derived1.output"
  "${clang_delta_BINARY_DIR}/tests/replace-derived-class/replace-derived1.output"
  COPYONLY
)

configure_file(
  "${clang_delta_SOURCE_DIR}/tests/replace-derived-class/replace-derived2.cpp"
  "${clang_delta_BINARY_DIR}/tests/replace-derived-class/replace-derived2.cpp"
  COPYONLY
)

configure_file(
  "${clang_delta_SOURCE_DIR}/tests/replace-derived-class/replace-derived2.output"
  "${clang_delta_BINARY_DIR}/tests/replace-derived-class/replace-derived2.output"
  COPYONLY
)

configure_file(
  "${clang_delta_SOURCE_DIR}/tests/replace-derived-class/replace-derived3.cpp"
  "${clang_delta_BINARY_DIR}/tests/replace-derived-class/replace-derived3.cpp"
  COPYONLY
)

configure_file(
  "${clang_delta_SOURCE_DIR}/tests/replace-derived-class/replace-derived3.output"
  "${clang_delta_BINARY_DIR}/tests/replace-derived-class/replace-derived3.output"
  COPYONLY
)

configure_file(
  "${clang_delta_SOURCE_DIR}/tests/replace-derived-class/replace-derived4.cpp"
  "${clang_delta_BINARY_DIR}/tests/replace-derived-class/replace-derived4.cpp"
  COPYONLY
)

configure_file(
  "${clang_delta_SOURCE_DIR}/tests/replace-derived-class/replace-derived4.output"
  "${clang_delta_BINARY_DIR}/tests/replace-derived-class/replace-derived4.output"
  COPYONLY
)

configure_file(
  "${clang_delta_SOURCE_DIR}/tests/replace-function-def-with-decl/macro1.c"
  "${clang_delta_BINARY_DIR}/tests/replace-function-def-with-decl/macro1.c"
  COPYONLY
)

configure_file(
  "${clang_delta_SOURCE_DIR}/tests/replace-function-def-with-decl/macro1.output"
  "${clang_delta_BINARY_DIR}/tests/replace-function-def-with-decl/macro1.output"
  COPYONLY
)

configure_file(
  "${clang_delta_SOURCE_DIR}/tests/replace-function-def-with-decl/macro2.c"
  "${clang_delta_BINARY_DIR}/tests/replace-function-def-with-decl/macro2.c"
  COPYONLY
)

configure_file(
  "${clang_delta_SOURCE_DIR}/tests/replace-function-def-with-decl/macro2.output"
  "${clang_delta_BINARY_DIR}/tests/replace-function-def-with-decl/macro2.output"
  COPYONLY
)

configure_file(
  "${clang_delta_SOURCE_DIR}/tests/return-void/test1.c"
  "${clang_delta_BINARY_DIR}/tests/return-void/test1.c"
  COPYONLY
)

configure_file(
  "${clang_delta_SOURCE_DIR}/tests/return-void/test1.output"
  "${clang_delta_BINARY_DIR}/tests/return-void/test1.output"
  COPYONLY
)

configure_file(
  "${clang_delta_SOURCE_DIR}/tests/return-void/test1.cc"
  "${clang_delta_BINARY_DIR}/tests/return-void/test1.cc"
  COPYONLY
)

configure_file(
  "${clang_delta_SOURCE_DIR}/tests/return-void/test1.output"
  "${clang_delta_BINARY_DIR}/tests/return-void/test1.output"
  COPYONLY
)

configure_file(
  "${clang_delta_SOURCE_DIR}/tests/return-void/test2.c"
  "${clang_delta_BINARY_DIR}/tests/return-void/test2.c"
  COPYONLY
)

configure_file(
  "${clang_delta_SOURCE_DIR}/tests/return-void/test2.output"
  "${clang_delta_BINARY_DIR}/tests/return-void/test2.output"
  COPYONLY
)

configure_file(
  "${clang_delta_SOURCE_DIR}/tests/return-void/test3.c"
  "${clang_delta_BINARY_DIR}/tests/return-void/test3.c"
  COPYONLY
)

configure_file(
  "${clang_delta_SOURCE_DIR}/tests/return-void/test3.output"
  "${clang_delta_BINARY_DIR}/tests/return-void/test3.output"
  COPYONLY
)

configure_file(
  "${clang_delta_SOURCE_DIR}/tests/return-void/test4.c"
  "${clang_delta_BINARY_DIR}/tests/return-void/test4.c"
  COPYONLY
)

configure_file(
  "${clang_delta_SOURCE_DIR}/tests/return-void/test4.output"
  "${clang_delta_BINARY_DIR}/tests/return-void/test4.output"
  COPYONLY
)

configure_file(
  "${clang_delta_SOURCE_DIR}/tests/return-void/test5.c"
  "${clang_delta_BINARY_DIR}/tests/return-void/test5.c"
  COPYONLY
)

configure_file(
  "${clang_delta_SOURCE_DIR}/tests/return-void/test5.output"
  "${clang_delta_BINARY_DIR}/tests/return-void/test5.output"
  COPYONLY
)

configure_file(
  "${clang_delta_SOURCE_DIR}/tests/return-void/test6.c"
  "${clang_delta_BINARY_DIR}/tests/return-void/test6.c"
  COPYONLY
)

configure_file(
  "${clang_delta_SOURCE_DIR}/tests/return-void/test6.output"
  "${clang_delta_BINARY_DIR}/tests/return-void/test6.output"
  COPYONLY
)

configure_file(
  "${clang_delta_SOURCE_DIR}/tests/simplify-callexpr/macro.c"
  "${clang_delta_BINARY_DIR}/tests/simplify-callexpr/macro.c"
  COPYONLY
)

configure_file(
  "${clang_delta_SOURCE_DIR}/tests/simplify-callexpr/macro.output"
  "${clang_delta_BINARY_DIR}/tests/simplify-callexpr/macro.output"
  COPYONLY
)

configure_file(
  "${clang_delta_SOURCE_DIR}/tests/simplify-callexpr/test.c"
  "${clang_delta_BINARY_DIR}/tests/simplify-callexpr/test.c"
  COPYONLY
)

configure_file(
  "${clang_delta_SOURCE_DIR}/tests/simplify-callexpr/test.output"
  "${clang_delta_BINARY_DIR}/tests/simplify-callexpr/test.output"
  COPYONLY
)

configure_file(
  "${clang_delta_SOURCE_DIR}/tests/simplify-callexpr/test2.c"
  "${clang_delta_BINARY_DIR}/tests/simplify-callexpr/test2.c"
  COPYONLY
)

configure_file(
  "${clang_delta_SOURCE_DIR}/tests/simplify-callexpr/test2.output"
  "${clang_delta_BINARY_DIR}/tests/simplify-callexpr/test2.output"
  COPYONLY
)

configure_file(
  "${clang_delta_SOURCE_DIR}/tests/simplify-if/macro.c"
  "${clang_delta_BINARY_DIR}/tests/simplify-if/macro.c"
  COPYONLY
)

configure_file(
  "${clang_delta_SOURCE_DIR}/tests/simplify-if/macro.output"
  "${clang_delta_BINARY_DIR}/tests/simplify-if/macro.output"
  COPYONLY
)

configure_file(
  "${clang_delta_SOURCE_DIR}/tests/union-to-struct/union1.c"
  "${clang_delta_BINARY_DIR}/tests/union-to-struct/union1.c"
  COPYONLY
)

configure_file(
  "${clang_delta_SOURCE_DIR}/tests/union-to-struct/union1.output"
  "${clang_delta_BINARY_DIR}/tests/union-to-struct/union1.output"
  COPYONLY
)

configure_file(
  "${clang_delta_SOURCE_DIR}/tests/union-to-struct/union2.c"
  "${clang_delta_BINARY_DIR}/tests/union-to-struct/union2.c"
  COPYONLY
)

configure_file(
  "${clang_delta_SOURCE_DIR}/tests/union-to-struct/union2.output"
  "${clang_delta_BINARY_DIR}/tests/union-to-struct/union2.output"
  COPYONLY
)

configure_file(
  "${clang_delta_SOURCE_DIR}/tests/union-to-struct/union3.c"
  "${clang_delta_BINARY_DIR}/tests/union-to-struct/union3.c"
  COPYONLY
)

configure_file(
  "${clang_delta_SOURCE_DIR}/tests/union-to-struct/union3.output"
  "${clang_delta_BINARY_DIR}/tests/union-to-struct/union3.output"
  COPYONLY
)

# Add flags for compiling against LLVM.
#
add_definitions(${LLVM_DEFINITIONS})
set_property(DIRECTORY APPEND PROPERTY COMPILE_DEFINITIONS
  $<$<CONFIG:Release>:NDEBUG>)
# include_directories(${PROJECT_BINARY_DIR}) --- if we generated .h files here
include_directories(${CMAKE_BINARY_DIR})
include_directories(${PROJECT_SOURCE_DIR}) # needed for gen'ed .cpp files
include_directories(${LLVM_INCLUDE_DIRS})
include_directories(${CLANG_INCLUDE_DIRS}) # only works for LLVM post-4.0

link_directories(${LLVM_LIBRARY_DIRS})

# ENE: Note that LLVM_LIBS is unused.
#
# The CLANG_LIBS defined below depend on various LLVM libraries.  When we do
# `target_link_libraries(clang_delta ${CLANG_LIBS})`, CMake's automatic library
# dependency tracking adds ("is expected to add") the necessary LLVM libraries
# and other libraries to the link set without us doing anything special.
#
# There are reports that this automatic tracking does not always work.  If this
# is the case for you, you can try adding LLVM_LIBS to the invocation of
# `target_link_libraries()` later in this file.  There are reports that
# sometimes this doesn't solve the problem, so caveat emptor.
#
# There are reports that including LLVM_LIBS in `target_link_libraries()`, when
# it is not needed, can cause dynamic link errors when `clang_delta` is run
# (multiply defined symbols).  This is another reason why we don't include
# LLVM_LIBS in the `target_link_libraries()` call by default.
#
llvm_map_components_to_libnames(LLVM_LIBS
  coverage
  irreader
  mcparser
  objcarcopts
  option
  passes
  profiledata
  support
)

set(CLANG_LIBS
  clang-cpp
  LLVM
)

add_executable(clang_delta
  ${CMAKE_BINARY_DIR}/config.h
  AggregateToScalar.cpp
  AggregateToScalar.h
  BinOpSimplification.cpp
  BinOpSimplification.h
  CallExprToValue.cpp
  CallExprToValue.h
  ClangDelta.cpp
  ClassTemplateToClass.cpp
  ClassTemplateToClass.h
  CombineGlobalVarDecl.cpp
  CombineGlobalVarDecl.h
  CombineLocalVarDecl.cpp
  CombineLocalVarDecl.h
  CommonParameterRewriteVisitor.h
  CommonRenameClassRewriteVisitor.h
  CommonStatementVisitor.h
  CommonTemplateArgumentVisitor.h
  CopyPropagation.cpp
  CopyPropagation.h
  EmptyStructToInt.cpp
  EmptyStructToInt.h
  ExpressionDetector.cpp
  ExpressionDetector.h
  InstantiateTemplateParam.cpp
  InstantiateTemplateParam.h
  InstantiateTemplateTypeParamToInt.cpp
  InstantiateTemplateTypeParamToInt.h
  LiftAssignmentExpr.cpp
  LiftAssignmentExpr.h
  LocalToGlobal.cpp
  LocalToGlobal.h
  MoveFunctionBody.cpp
  MoveFunctionBody.h
  MoveGlobalVar.cpp
  MoveGlobalVar.h
  ParamToGlobal.cpp
  ParamToGlobal.h
  ParamToLocal.cpp
  ParamToLocal.h
  ReduceArrayDim.cpp
  ReduceArrayDim.h
  ReduceArraySize.cpp
  ReduceArraySize.h
  ReduceClassTemplateParameter.cpp
  ReduceClassTemplateParameter.h
  ReducePointerLevel.cpp
  ReducePointerLevel.h
  ReducePointerPairs.cpp
  ReducePointerPairs.h
  RemoveAddrTaken.cpp
  RemoveAddrTaken.h
  RemoveArray.cpp
  RemoveArray.h
  RemoveBaseClass.cpp
  RemoveBaseClass.h
  RemoveCtorInitializer.cpp
  RemoveCtorInitializer.h
  RemoveEnumMemberValue.cpp
  RemoveEnumMemberValue.h
  RemoveNamespace.cpp
  RemoveNamespace.h
  RemoveNestedFunction.cpp
  RemoveNestedFunction.h
  RemovePointer.cpp
  RemovePointer.h
  RemoveTrivialBaseTemplate.cpp
  RemoveTrivialBaseTemplate.h
  RemoveUnresolvedBase.cpp
  RemoveUnresolvedBase.h
  RemoveUnusedEnumMember.cpp
  RemoveUnusedEnumMember.h
  RemoveUnusedFunction.cpp
  RemoveUnusedFunction.h
  RemoveUnusedOuterClass.cpp
  RemoveUnusedOuterClass.h
  RemoveUnusedStructField.cpp
  RemoveUnusedStructField.h
  RemoveUnusedVar.cpp
  RemoveUnusedVar.h
  RenameCXXMethod.cpp
  RenameCXXMethod.h
  RenameClass.cpp
  RenameClass.h
  RenameFun.cpp
  RenameFun.h
  RenameParam.cpp
  RenameParam.h
  RenameVar.cpp
  RenameVar.h
  ReplaceArrayAccessWithIndex.cpp
  ReplaceArrayAccessWithIndex.h
  ReplaceArrayIndexVar.cpp
  ReplaceArrayIndexVar.h
  ReplaceCallExpr.cpp
  ReplaceCallExpr.h
  ReplaceClassWithBaseTemplateSpec.cpp
  ReplaceClassWithBaseTemplateSpec.h
  ReplaceDependentName.cpp
  ReplaceDependentName.h
  ReplaceDependentTypedef.cpp
  ReplaceDependentTypedef.h
  ReplaceDerivedClass.cpp
  ReplaceDerivedClass.h
  ReplaceFunctionDefWithDecl.cpp
  ReplaceFunctionDefWithDecl.h
  ReplaceOneLevelTypedefType.cpp
  ReplaceOneLevelTypedefType.h
  ReplaceSimpleTypedef.cpp
  ReplaceSimpleTypedef.h
  ReplaceUndefinedFunction.cpp
  ReplaceUndefinedFunction.h
  ReturnVoid.cpp
  ReturnVoid.h
  RewriteUtils.cpp
  RewriteUtils.h
  SimpleInliner.cpp
  SimpleInliner.h
  SimplifyCallExpr.cpp
  SimplifyCallExpr.h
  SimplifyCommaExpr.cpp
  SimplifyCommaExpr.h
  SimplifyDependentTypedef.cpp
  SimplifyDependentTypedef.h
  SimplifyIf.cpp
  SimplifyIf.h
  SimplifyNestedClass.cpp
  SimplifyNestedClass.h
  SimplifyRecursiveTemplateInstantiation.cpp
  SimplifyRecursiveTemplateInstantiation.h
  SimplifyStruct.cpp
  SimplifyStruct.h
  SimplifyStructUnionDecl.cpp
  SimplifyStructUnionDecl.h
  TemplateArgToInt.cpp
  TemplateArgToInt.h
  TemplateNonTypeArgToInt.cpp
  TemplateNonTypeArgToInt.h
  Transformation.cpp
  Transformation.h
  TransformationManager.cpp
  TransformationManager.h
  UnifyFunctionDecl.cpp
  UnifyFunctionDecl.h
  UnionToStruct.cpp
  UnionToStruct.h
  VectorToArray.cpp
  VectorToArray.h
  ${PROJECT_BINARY_DIR}/git_version.cpp
  git_version.h
)

# ENE: See comment above about why LLVM_LIBS is not included in this call.
target_link_libraries(clang_delta ${CLANG_LIBS})

# For cases in which the LLVM libraries are shared libraries, remember where
# the shared libraries are.
set_target_properties(clang_delta
  PROPERTIES
  BUILD_WITH_INSTALL_RPATH "yes"
  INSTALL_RPATH "${LLVM_LIBRARY_DIRS}"
)

# On Windows, we also need to link with "Version.dll" system library.
# See <https://github.com/csmith-project/creduce/pull/126>.
if("${CMAKE_SYSTEM_NAME}" STREQUAL "Windows")
  target_link_libraries(clang_delta Version)
endif()

install(TARGETS clang_delta
  RUNTIME DESTINATION
)
# If binary is read-only, then installing may fail with an error:
# CMake Error at cmake_install.cmake:45 (FILE):
#  file RPATH_REMOVE could not remove RPATH from file:
#    /disk2/randtest/install/libexec/clang_delta
#  Error opening file for update.
#
# Do I want RPATH at all?  We can turn it off, by setting CMAKE_SKIP_RPATH
# https://cmake.org/cmake/help/v2.8.8/cmake.html#variable%3aCMAKE_SKIP_RPATH
# See also the stuff about RPATH for `set_target_properties', which I don't
# really grok:
# https://cmake.org/cmake/help/v2.8.8/cmake.html#command:set_target_properties
#
#  PERMISSIONS
#    OWNER_READ OWNER_EXECUTE GROUP_READ GROUP_EXECUTE WORLD_READ WORLD_EXECUTE

#####

###############################################################################

## End of file.

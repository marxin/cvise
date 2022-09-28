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

function(configure_one_file path)
  configure_file(
    "${clang_delta_SOURCE_DIR}/${path}"
    "${clang_delta_BINARY_DIR}/${path}"
    COPYONLY
  )
endfunction(configure_one_file)

set(SOURCE_FILES
  "/tests/test_clang_delta.py"
  "/tests/aggregate-to-scalar/cast.c"
  "/tests/aggregate-to-scalar/cast.output"
  "/tests/aggregate-to-scalar/test1.c"
  "/tests/aggregate-to-scalar/test1.output"
  "/tests/aggregate-to-scalar/test2.c"
  "/tests/aggregate-to-scalar/test2.output"
  "/tests/aggregate-to-scalar/test3.c"
  "/tests/aggregate-to-scalar/test3.output"
  "/tests/aggregate-to-scalar/test4.c"
  "/tests/aggregate-to-scalar/test4.output"
  "/tests/aggregate-to-scalar/test5.cc"
  "/tests/aggregate-to-scalar/test5.output"
  "/tests/aggregate-to-scalar/test6.cc"
  "/tests/aggregate-to-scalar/test6.output"
  "/tests/callexpr-to-value/macro1.c"
  "/tests/callexpr-to-value/macro1.output"
  "/tests/callexpr-to-value/macro2.c"
  "/tests/callexpr-to-value/macro2.output"
  "/tests/callexpr-to-value/test1.c"
  "/tests/callexpr-to-value/test1.output"
  "/tests/callexpr-to-value/test2.c"
  "/tests/callexpr-to-value/test2.output"
  "/tests/class-to-struct/class-to-struct1.C"
  "/tests/class-to-struct/class-to-struct1.output"
  "/tests/class-to-struct/class-to-struct-forward.C"
  "/tests/class-template-to-class/test1.cc"
  "/tests/class-template-to-class/test1.output"
  "/tests/copy-propagation/copy1.cpp"
  "/tests/copy-propagation/copy1.output"
  "/tests/copy-propagation/copy2.cpp"
  "/tests/copy-propagation/copy2.output"
  "/tests/empty-struct-to-int/empty-struct.cpp"
  "/tests/empty-struct-to-int/empty-struct.output"
  "/tests/empty-struct-to-int/empty-struct2.cpp"
  "/tests/empty-struct-to-int/empty-struct2.output"
  "/tests/empty-struct-to-int/empty-struct3.cpp"
  "/tests/empty-struct-to-int/empty-struct3.output"
  "/tests/empty-struct-to-int/empty-struct4.cpp"
  "/tests/empty-struct-to-int/empty-struct4.output"
  "/tests/empty-struct-to-int/empty-struct5.cpp"
  "/tests/empty-struct-to-int/empty-struct5.output"
  "/tests/empty-struct-to-int/empty-struct6.c"
  "/tests/empty-struct-to-int/empty-struct6.output"
  "/tests/empty-struct-to-int/empty-struct7.c"
  "/tests/empty-struct-to-int/empty-struct7.output"
  "/tests/empty-struct-to-int/struct_int.c"
  "/tests/empty-struct-to-int/struct_int.output"
  "/tests/empty-struct-to-int/test1.cc"
  "/tests/empty-struct-to-int/test1.output"
  "/tests/empty-struct-to-int/test2.cc"
  "/tests/empty-struct-to-int/test2.output"
  "/tests/empty-struct-to-int/test3.c"
  "/tests/empty-struct-to-int/test3.output"
  "/tests/instantiate-template-param/default_param.cc"
  "/tests/instantiate-template-param/default_param.output"
  "/tests/instantiate-template-param/test1.cc"
  "/tests/instantiate-template-param/test1.output"
  "/tests/instantiate-template-param/test2.cc"
  "/tests/instantiate-template-param/test2.output"
  "/tests/instantiate-template-param/test3.cc"
  "/tests/instantiate-template-param/test4.cc"
  "/tests/instantiate-template-param/test4.output"
  "/tests/local-to-global/macro.c"
  "/tests/local-to-global/macro.output"
  "/tests/local-to-global/unnamed_1.c"
  "/tests/local-to-global/unnamed_1.output"
  "/tests/local-to-global/unnamed_2.c"
  "/tests/local-to-global/unnamed_2.output"
  "/tests/local-to-global/unnamed_3.c"
  "/tests/local-to-global/unnamed_3.output"
  "/tests/param-to-global/macro.c"
  "/tests/param-to-global/macro.output"
  "/tests/reduce-array-dim/non-type-temp-arg.cpp"
  "/tests/reduce-array-dim/non-type-temp-arg.output"
  "/tests/reduce-pointer-level/scalar-init-expr.cpp"
  "/tests/reduce-pointer-level/scalar-init-expr.output"
  "/tests/remove-namespace/macro.cpp"
  "/tests/remove-namespace/macro.output"
  "/tests/remove-namespace/macro.output2"
  "/tests/remove-namespace/macro.output3"
  "/tests/remove-namespace/macro.output4"
  "/tests/remove-namespace/macro.output5"
  "/tests/remove-namespace/namespace.cpp"
  "/tests/remove-namespace/namespace.output"
  "/tests/remove-namespace/namespace.output2"
  "/tests/remove-namespace/namespace.output3"
  "/tests/remove-namespace/namespace2.cpp"
  "/tests/remove-namespace/namespace2.output"
  "/tests/remove-namespace/namespace2.output2"
  "/tests/remove-namespace/namespace3.cpp"
  "/tests/remove-namespace/namespace3.output"
  "/tests/remove-namespace/namespace3.output2"
  "/tests/remove-namespace/namespace3.output3"
  "/tests/remove-namespace/namespace4.cpp"
  "/tests/remove-namespace/namespace4.output"
  "/tests/remove-namespace/namespace5.cpp"
  "/tests/remove-namespace/namespace5.output"
  "/tests/remove-namespace/namespace5.output2"
  "/tests/remove-namespace/namespace5.output3"
  "/tests/remove-namespace/namespace5.output4"
  "/tests/remove-namespace/namespace6.cpp"
  "/tests/remove-namespace/namespace6.output"
  "/tests/remove-namespace/namespace6.output2"
  "/tests/remove-namespace/namespace7.cpp"
  "/tests/remove-namespace/namespace7.output"
  "/tests/remove-namespace/namespace7.output2"
  "/tests/remove-namespace/namespace7.output3"
  "/tests/remove-namespace/namespace8.cpp"
  "/tests/remove-namespace/namespace8.output"
  "/tests/remove-namespace/namespace8.output2"
  "/tests/remove-namespace/namespace9.cpp"
  "/tests/remove-namespace/namespace9.output"
  "/tests/remove-namespace/namespace10.cpp"
  "/tests/remove-namespace/namespace10.output"
  "/tests/remove-namespace/namespace10.output2"
  "/tests/remove-namespace/namespace11.cpp"
  "/tests/remove-namespace/namespace11.output"
  "/tests/remove-namespace/namespace11.output2"
  "/tests/remove-namespace/namespace12.cpp"
  "/tests/remove-namespace/namespace12.output"
  "/tests/remove-namespace/namespace12.output2"
  "/tests/remove-namespace/namespace12.output3"
  "/tests/remove-namespace/namespace13.cpp"
  "/tests/remove-namespace/namespace13.output"
  "/tests/remove-namespace/namespace13.output2"
  "/tests/remove-namespace/namespace14.cpp"
  "/tests/remove-namespace/namespace14.output"
  "/tests/remove-namespace/namespace15.cpp"
  "/tests/remove-namespace/namespace15.output"
  "/tests/remove-namespace/namespace15.output2"
  "/tests/remove-namespace/namespace15.output3"
  "/tests/remove-enum-member-value/builtin_macro.c"
  "/tests/remove-enum-member-value/builtin_macro.output"
  "/tests/remove-unused-enum-member/range.c"
  "/tests/remove-unused-enum-member/range.output"
  "/tests/remove-nested-function/remove_nested_func1.cc"
  "/tests/remove-nested-function/remove_nested_func1.output"
  "/tests/remove-try-catch/try-catch-1.cpp"
  "/tests/remove-try-catch/try-catch-1.output"
  "/tests/remove-try-catch/try-catch-2.cpp"
  "/tests/remove-try-catch/try-catch-2.output"
  "/tests/remove-unused-field/designated1.c"
  "/tests/remove-unused-field/designated1.output"
  "/tests/remove-unused-field/designated2.c"
  "/tests/remove-unused-field/designated2.output"
  "/tests/remove-unused-field/designated3.c"
  "/tests/remove-unused-field/designated3.output"
  "/tests/remove-unused-field/designated4.c"
  "/tests/remove-unused-field/designated4.output"
  "/tests/remove-unused-field/designated5.c"
  "/tests/remove-unused-field/designated5.output"
  "/tests/remove-unused-field/unused_field1.c"
  "/tests/remove-unused-field/unused_field1.output"
  "/tests/remove-unused-field/unused_field2.c"
  "/tests/remove-unused-field/unused_field2.output"
  "/tests/remove-unused-field/unused_field3.cpp"
  "/tests/remove-unused-field/unused_field3.output"
  "/tests/remove-unused-function/class.cc"
  "/tests/remove-unused-function/class.output"
  "/tests/remove-unused-function/const.cc"
  "/tests/remove-unused-function/const.output"
  "/tests/remove-unused-function/const.output2"
  "/tests/remove-unused-function/default.cc"
  "/tests/remove-unused-function/default.output"
  "/tests/remove-unused-function/default.output2"
  "/tests/remove-unused-function/delete.cc"
  "/tests/remove-unused-function/delete.output"
  "/tests/remove-unused-function/delete2.cc"
  "/tests/remove-unused-function/delete2.output"
  "/tests/remove-unused-function/delete2.output2"
  "/tests/remove-unused-function/delete2.output3"
  "/tests/remove-unused-function/delete2.output4"
  "/tests/remove-unused-function/inline_ns.cc"
  "/tests/remove-unused-function/inline_ns.output"
  "/tests/remove-unused-function/macro1.cc"
  "/tests/remove-unused-function/macro1.output"
  "/tests/remove-unused-function/macro2.cc"
  "/tests/remove-unused-function/macro2.output"
  "/tests/remove-unused-function/macro3.cc"
  "/tests/remove-unused-function/macro3.output"
  "/tests/remove-unused-function/template1.cc"
  "/tests/remove-unused-function/template1.output"
  "/tests/remove-unused-function/template2.cc"
  "/tests/remove-unused-function/template2.output"
  "/tests/remove-unused-function/unused-funcs.cc"
  "/tests/remove-unused-function/unused-funcs.output"
  "/tests/remove-unused-var/struct1.c"
  "/tests/remove-unused-var/struct1.output"
  "/tests/remove-unused-var/struct2.c"
  "/tests/remove-unused-var/struct2.output"
  "/tests/remove-unused-var/unused_var.cpp"
  "/tests/remove-unused-var/unused_var.output"
  "/tests/rename-class/base_specifier.cpp"
  "/tests/rename-class/base_specifier.output"
  "/tests/rename-class/bool.cc"
  "/tests/rename-class/bool.output"
  "/tests/rename-class/class_template.cc"
  "/tests/rename-class/class_template.output"
  "/tests/rename-class/class_template2.cc"
  "/tests/rename-class/class_template2.output"
  "/tests/rename-class/dependent.cpp"
  "/tests/rename-class/dependent.output"
  "/tests/rename-class/dependent_name.cpp"
  "/tests/rename-class/dependent_name.output"
  "/tests/rename-class/derive.cc"
  "/tests/rename-class/derive.output"
  "/tests/rename-class/dtor.cc"
  "/tests/rename-class/dtor.output"
  "/tests/rename-class/dtor1.cc"
  "/tests/rename-class/dtor1.output"
  "/tests/rename-class/elaborated_type1.cpp"
  "/tests/rename-class/elaborated_type1.output"
  "/tests/rename-class/elaborated_type2.cpp"
  "/tests/rename-class/elaborated_type2.output"
  "/tests/rename-class/explicit_specialization.cpp"
  "/tests/rename-class/explicit_specialization.output"
  "/tests/rename-class/forward_decl.cc"
  "/tests/rename-class/forward_decl.output"
  "/tests/rename-class/injected_name.cpp"
  "/tests/rename-class/injected_name.output"
  "/tests/rename-class/instantiation.cpp"
  "/tests/rename-class/instantiation.output"
  "/tests/rename-class/parm.cpp"
  "/tests/rename-class/parm.output"
  "/tests/rename-class/partial_specialization.cpp"
  "/tests/rename-class/partial_specialization.output"
  "/tests/rename-class/rename-class1.cpp"
  "/tests/rename-class/rename-class1.output"
  "/tests/rename-class/rename-class2.cpp"
  "/tests/rename-class/rename-class2.output"
  "/tests/rename-class/specialization.cpp"
  "/tests/rename-class/specialization.output"
  "/tests/rename-class/static_member.cc"
  "/tests/rename-class/static_member.output"
  "/tests/rename-class/template_class_1.cpp"
  "/tests/rename-class/template_class_1.output"
  "/tests/rename-class/template_parm.cpp"
  "/tests/rename-class/template_parm.output"
  "/tests/rename-class/template_template.cpp"
  "/tests/rename-class/template_template.output"
  "/tests/rename-class/template_template_parm.cpp"
  "/tests/rename-class/template_template_parm.output"
  "/tests/rename-class/typedef.cpp"
  "/tests/rename-class/typedef.output"
  "/tests/rename-class/typedef2.cc"
  "/tests/rename-class/typedef2.output"
  "/tests/rename-class/using.cpp"
  "/tests/rename-class/using.output"
  "/tests/rename-class/using1.cc"
  "/tests/rename-class/using1.output"
  "/tests/rename-cxx-method/overloaded.cc"
  "/tests/rename-cxx-method/overloaded.output"
  "/tests/rename-cxx-method/test1.cc"
  "/tests/rename-cxx-method/test1.output"
  "/tests/rename-cxx-method/test2.cc"
  "/tests/rename-cxx-method/test2.output"
  "/tests/rename-cxx-method/test3.cc"
  "/tests/rename-cxx-method/test3.output"
  "/tests/rename-fun/func_templ.cc"
  "/tests/rename-fun/func_templ.output"
  "/tests/rename-fun/overloaded.cc"
  "/tests/rename-fun/overloaded.output"
  "/tests/rename-fun/test1.c"
  "/tests/rename-fun/test1.output"
  "/tests/rename-fun/multi.c"
  "/tests/rename-fun/multi.output"
  "/tests/rename-operator/test1.cc"
  "/tests/rename-operator/test1.output"
  "/tests/rename-operator/test2.cc"
  "/tests/rename-operator/test2.output"
  "/tests/rename-param/invalid.c"
  "/tests/rename-param/invalid.output"
  "/tests/rename-param/stuck.ii"
  "/tests/rename-var/rename-var.c"
  "/tests/rename-var/rename-var.output"
  "/tests/replace-derived-class/replace-derived1.cpp"
  "/tests/replace-derived-class/replace-derived1.output"
  "/tests/replace-derived-class/replace-derived2.cpp"
  "/tests/replace-derived-class/replace-derived2.output"
  "/tests/replace-derived-class/replace-derived3.cpp"
  "/tests/replace-derived-class/replace-derived3.output"
  "/tests/replace-derived-class/replace-derived4.cpp"
  "/tests/replace-derived-class/replace-derived4.output"
  "/tests/replace-function-def-with-decl/macro1.c"
  "/tests/replace-function-def-with-decl/macro1.output"
  "/tests/replace-function-def-with-decl/macro2.c"
  "/tests/replace-function-def-with-decl/macro2.output"
  "/tests/replace-function-def-with-decl/simple.cpp"
  "/tests/replace-function-def-with-decl/simple.cpp.preserve_foo.output"
  "/tests/replace-function-def-with-decl/simple.cpp.preserve_missing.output"
  "/tests/replace-function-def-with-decl/simple.cpp.preserve_quack.output"
  "/tests/replace-simple-typedef/test1.cc"
  "/tests/replace-simple-typedef/test1.output"
  "/tests/replace-simple-typedef/test2.cc"
  "/tests/replace-simple-typedef/test2.output"
  "/tests/return-void/test1.c"
  "/tests/return-void/test1.output"
  "/tests/return-void/test2.c"
  "/tests/return-void/test2.output"
  "/tests/return-void/test3.c"
  "/tests/return-void/test3.output"
  "/tests/return-void/test4.c"
  "/tests/return-void/test4.output"
  "/tests/return-void/test5.c"
  "/tests/return-void/test5.output"
  "/tests/return-void/test6.c"
  "/tests/return-void/test6.output"
  "/tests/return-void/test7.cc"
  "/tests/return-void/test7.output"
  "/tests/return-void/test8.cc"
  "/tests/return-void/test8.output"
  "/tests/return-void/test9.c"
  "/tests/return-void/test9.output"
  "/tests/simplify-callexpr/macro.c"
  "/tests/simplify-callexpr/macro.output"
  "/tests/simplify-callexpr/test.c"
  "/tests/simplify-callexpr/test.output"
  "/tests/simplify-callexpr/test2.c"
  "/tests/simplify-callexpr/test2.output"
  "/tests/simplify-if/macro.c"
  "/tests/simplify-if/macro.output"
  "/tests/simplify-recursive-template-instantiation/test.cc"
  "/tests/simplify-recursive-template-instantiation/test.output"
  "/tests/template-arg-to-int/not_valid5.cc"
  "/tests/union-to-struct/union1.c"
  "/tests/union-to-struct/union1.output"
  "/tests/union-to-struct/union2.c"
  "/tests/union-to-struct/union2.output"
  "/tests/union-to-struct/union3.c"
  "/tests/union-to-struct/union3.output"
  "/tests/simple-inliner/alias-crash.c"
  "/tests/simple-inliner/alias-crash.output"
  "/tests/member-to-global/test1.cc"
  "/tests/member-to-global/test1.output"
  "/tests/member-to-global/test2.cc"
  "/tests/member-to-global/test2.output"
  "/tests/member-to-global/test3.cc"
  "/tests/member-to-global/test3.output"
  "/tests/member-to-global/test4.cc"
  "/tests/member-to-global/test4.output"
  "/tests/member-to-global/test5.cc"
  "/tests/member-to-global/test5.output"
  "/tests/member-to-global/test6.cc"
  "/tests/member-to-global/test6.output"
  "/tests/member-to-global/test7.cc"
  "/tests/member-to-global/test7.output"
)

foreach(file IN LISTS SOURCE_FILES)
  configure_one_file(${file})
endforeach()

if (MSVC)
  # Allow big object
  add_definitions(/bigobj)
  # Enable parallel builds
  add_definitions(/MP)
endif (MSVC)

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

if (${LLVM_LINK_LLVM_DYLIB})
  set(CLANG_LIBS
    clang-cpp
    LLVM
  )
else()
  set(CLANG_LIBS
    clangAST
    clangBasic
    clangFrontend
    clangParse
    clangLex
    clangRewrite
  )
endif()

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
  ClassToStruct.cpp
  ClassToStruct.h
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
  MemberToGlobal.cpp
  MemberToGlobal.h
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
  RemoveTryCatch.cpp
  RemoveTryCatch.h
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
  RenameOperator.cpp
  RenameOperator.h
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

if(MSVC)
  set(msvc_warning_flags
    # Disabled warnings.
    -wd4141 # Suppress ''modifier' : used more than once' (because of __forceinline combined with inline)
    -wd4146 # Suppress 'unary minus operator applied to unsigned type, result still unsigned'
    -wd4244 # Suppress ''argument' : conversion from 'type1' to 'type2', possible loss of data'
    -wd4267 # Suppress ''var' : conversion from 'size_t' to 'type', possible loss of data'
    -wd4291 # Suppress ''declaration' : no matching operator delete found; memory will not be freed if initialization throws an exception'
    -wd4351 # Suppress 'new behavior: elements of array 'array' will be default initialized'
    -wd4456 # Suppress 'declaration of 'var' hides local variable'
    -wd4457 # Suppress 'declaration of 'var' hides function parameter'
    -wd4458 # Suppress 'declaration of 'var' hides class member'
    -wd4459 # Suppress 'declaration of 'var' hides global declaration'
    -wd4503 # Suppress ''identifier' : decorated name length exceeded, name was truncated'
    -wd4624 # Suppress ''derived class' : destructor could not be generated because a base class destructor is inaccessible'
    -wd4722 # Suppress 'function' : destructor never returns, potential memory leak
    -wd4100 # Suppress 'unreferenced formal parameter'
    -wd4127 # Suppress 'conditional expression is constant'
    -wd4512 # Suppress 'assignment operator could not be generated'
    -wd4505 # Suppress 'unreferenced local function has been removed'
    -wd4610 # Suppress '<class> can never be instantiated'
    -wd4510 # Suppress 'default constructor could not be generated'
    -wd4702 # Suppress 'unreachable code'
    -wd4245 # Suppress ''conversion' : conversion from 'type1' to 'type2', signed/unsigned mismatch'
    -wd4706 # Suppress 'assignment within conditional expression'
    -wd4310 # Suppress 'cast truncates constant value'
    -wd4701 # Suppress 'potentially uninitialized local variable'
    -wd4703 # Suppress 'potentially uninitialized local pointer variable'
    -wd4389 # Suppress 'signed/unsigned mismatch'
    -wd4611 # Suppress 'interaction between '_setjmp' and C++ object destruction is non-portable'
    -wd4805 # Suppress 'unsafe mix of type <type> and type <type> in operation'
    -wd4204 # Suppress 'nonstandard extension used : non-constant aggregate initializer'
    -wd4577 # Suppress 'noexcept used with no exception handling mode specified; termination on exception is not guaranteed'
    -wd4091 # Suppress 'typedef: ignored on left of '' when no variable is declared'
        # C4592 is disabled because of false positives in Visual Studio 2015
        # Update 1. Re-evaluate the usefulness of this diagnostic with Update 2.
    -wd4592 # Suppress ''var': symbol will be dynamically initialized (implementation limitation)
    -wd4319 # Suppress ''operator' : zero extending 'type' to 'type' of greater size'
        # C4709 is disabled because of a bug with Visual Studio 2017 as of
        # v15.8.8. Re-evaluate the usefulness of this diagnostic when the bug
        # is fixed.
    -wd4709 # Suppress comma operator within array index expression
    -wd4530 # C++ exception handler used, but unwind semantics are not enabled.

    # Ideally, we'd like this warning to be enabled, but even MSVC 2019 doesn't
    # support the 'aligned' attribute in the way that clang sources requires (for
    # any code that uses the LLVM_ALIGNAS macro), so this is must be disabled to
    # avoid unwanted alignment warnings.
    -wd4324 # Suppress 'structure was padded due to __declspec(align())'

    # Promoted warnings.
    -w14062 # Promote 'enumerator in switch of enum is not handled' to level 1 warning.

    # Promoted warnings to errors.
    -we4238 # Promote 'nonstandard extension used : class rvalue used as lvalue' to error.
    )

  foreach(flag ${msvc_warning_flags})
    set(CMAKE_C_FLAGS "${CMAKE_C_FLAGS} ${flag}")
    set(CMAKE_CXX_FLAGS "${CMAKE_C_FLAGS} ${flag}")
  endforeach(flag)
endif(MSVC)

# UndefinedBehaviourSanitizer
set(CMAKE_C_FLAGS_UBSAN
    "-fsanitize=undefined -g"
    CACHE STRING "Flags used by the C compiler during UndefinedBehaviourSanitizer builds."
    FORCE)
set(CMAKE_CXX_FLAGS_UBSAN
    "-fsanitize=undefined -g"
    CACHE STRING "Flags used by the C++ compiler during UndefinedBehaviourSanitizer builds."
    FORCE)

# AddressSanitizer
set(CMAKE_C_FLAGS_ASAN
    "-fsanitize=address -g"
    CACHE STRING "Flags used by the C compiler during AddressSanitizer builds."
    FORCE)
set(CMAKE_CXX_FLAGS_ASAN
    "-fsanitize=address -g"
    CACHE STRING "Flags used by the C++ compiler during AddressSanitizer builds."
    FORCE)

# Coverage builds
set(CMAKE_C_FLAGS_COVERAGE
    "--coverage"
    CACHE STRING "Flags used by the C compiler during coverage builds."
    FORCE)
set(CMAKE_CXX_FLAGS_COVERAGE
    "--coverage"
    CACHE STRING "Flags used by the C++ compiler during coverage builds."
    FORCE)


install(TARGETS clang_delta
  DESTINATION "${CMAKE_INSTALL_LIBEXECDIR}/${cvise_PACKAGE}/"
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

import os
import subprocess
import unittest


class TestClangDelta(unittest.TestCase):

    @classmethod
    def check_clang_delta(cls, testcase, arguments, output_file=None):
        current = os.path.dirname(__file__)
        binary = os.path.join(current, '../clang_delta')
        cmd = '%s %s %s' % (binary, os.path.join(current, testcase), arguments)
        output = subprocess.check_output(cmd, shell=True, encoding='utf8')
        if not output_file:
            output_file = os.path.splitext(testcase)[0] + '.output'
        with open(os.path.join(current, output_file)) as f:
            expected = f.read()
        assert output == expected

    @classmethod
    def check_query_instances(cls, testcase, arguments, expected):
        current = os.path.dirname(__file__)
        binary = os.path.join(current, '../clang_delta')
        cmd = '%s %s %s' % (binary, os.path.join(current, testcase), arguments)
        output = subprocess.check_output(cmd, shell=True, encoding='utf8')
        assert output.strip() == expected

    @classmethod
    def check_error_message(cls, testcase, arguments, error_message):
        current = os.path.dirname(__file__)
        binary = os.path.join(current, '../clang_delta')
        cmd = '%s %s %s' % (binary, os.path.join(current, testcase), arguments)
        proc = subprocess.run(cmd, shell=True, encoding='utf8', stdout=subprocess.PIPE)
        assert proc.returncode == 255
        assert proc.stdout.strip() == error_message

    def test_aggregate_to_scalar_cast(self):
        self.check_clang_delta('aggregate-to-scalar/cast.c', '--transformation=aggregate-to-scalar --counter=1')

    def test_aggregate_to_scalar_test1(self):
        self.check_clang_delta('aggregate-to-scalar/test1.c', '--transformation=aggregate-to-scalar --counter=1')

    def test_aggregate_to_scalar_test2(self):
        self.check_clang_delta('aggregate-to-scalar/test2.c', '--transformation=aggregate-to-scalar --counter=1')

    def test_aggregate_to_scalar_test3(self):
        self.check_clang_delta('aggregate-to-scalar/test3.c', '--transformation=aggregate-to-scalar --counter=1')

    def test_aggregate_to_scalar_test4(self):
        self.check_clang_delta('aggregate-to-scalar/test4.c', '--transformation=aggregate-to-scalar --counter=1')

    def test_aggregate_to_scalar_test5(self):
        self.check_clang_delta('aggregate-to-scalar/test5.cc', '--transformation=aggregate-to-scalar --counter=1')

    def test_aggregate_to_scalar_test6(self):
        self.check_clang_delta('aggregate-to-scalar/test6.cc', '--transformation=aggregate-to-scalar --counter=1')

    def test_callexpr_to_value_macro1(self):
        self.check_clang_delta('callexpr-to-value/macro1.c', '--transformation=callexpr-to-value --counter=1')

    def test_callexpr_to_value_macro2(self):
        self.check_clang_delta('callexpr-to-value/macro2.c', '--transformation=callexpr-to-value --counter=1')

    def test_callexpr_to_value_test1(self):
        self.check_clang_delta('callexpr-to-value/test1.c', '--transformation=callexpr-to-value --counter=1')

    def test_callexpr_to_value_test2(self):
        self.check_clang_delta('callexpr-to-value/test2.c', '--transformation=callexpr-to-value --counter=1')

    def test_copy_propagation_copy1(self):
        self.check_clang_delta('copy-propagation/copy1.cpp', '--transformation=copy-propagation --counter=1')

    def test_copy_propagation_copy2(self):
        self.check_clang_delta('copy-propagation/copy2.cpp', '--transformation=copy-propagation --counter=2')

    def test_empty_struct_to_int_empty_struct(self):
        self.check_clang_delta('empty-struct-to-int/empty-struct.cpp', '--transformation=empty-struct-to-int --counter=1')

    def test_empty_struct_to_int_empty_struct2(self):
        self.check_clang_delta('empty-struct-to-int/empty-struct2.cpp', '--transformation=empty-struct-to-int --counter=1')

    def test_empty_struct_to_int_empty_struct3(self):
        self.check_clang_delta('empty-struct-to-int/empty-struct3.cpp', '--transformation=empty-struct-to-int --counter=2')

    def test_empty_struct_to_int_empty_struct4(self):
        self.check_clang_delta('empty-struct-to-int/empty-struct4.cpp', '--transformation=empty-struct-to-int --counter=1')

    def test_empty_struct_to_int_empty_struct5(self):
        self.check_clang_delta('empty-struct-to-int/empty-struct5.cpp', '--transformation=empty-struct-to-int --counter=1')

    @unittest.skip(reason='Libclang segfault')
    def test_empty_struct_to_int_empty_struct6(self):
        self.check_clang_delta('empty-struct-to-int/empty-struct6.c', '--transformation=empty-struct-to-int --counter=1')

    def test_empty_struct_to_int_empty_struct7(self):
        self.check_clang_delta('empty-struct-to-int/empty-struct7.c', '--transformation=empty-struct-to-int --counter=1')

    def test_empty_struct_to_int_struct_int(self):
        self.check_clang_delta('empty-struct-to-int/struct_int.c', '--transformation=empty-struct-to-int --counter=1')

    def test_empty_struct_to_int_test1(self):
        self.check_clang_delta('empty-struct-to-int/test1.cc', '--transformation=empty-struct-to-int --counter=1')

    def test_empty_struct_to_int_test2(self):
        self.check_clang_delta('empty-struct-to-int/test2.cc', '--transformation=empty-struct-to-int --counter=1')

    def test_empty_struct_to_int_test3(self):
        self.check_clang_delta('empty-struct-to-int/test3.c', '--transformation=empty-struct-to-int --counter=1')

    def test_instantiate_template_param_default_param(self):
        self.check_clang_delta('instantiate-template-param/default_param.cc', '--transformation=instantiate-template-param --counter=1')

    def test_instantiate_template_param_default_test1(self):
        self.check_clang_delta('instantiate-template-param/test1.cc', '--transformation=instantiate-template-param --counter=1')

    def test_instantiate_template_param_default_test2(self):
        self.check_clang_delta('instantiate-template-param/test2.cc', '--transformation=instantiate-template-param --counter=1')

    def test_instantiate_template_param_default_test3(self):
        self.check_query_instances('instantiate-template-param/test3.cc', '--query-instances=instantiate-template-param',
                                   'Available transformation instances: 0')

    def test_local_to_global_macro(self):
        self.check_clang_delta('local-to-global/macro.c', '--transformation=local-to-global --counter=1')

    def test_local_to_global_unnamed_1(self):
        self.check_clang_delta('local-to-global/unnamed_1.c', '--transformation=local-to-global --counter=1')

    def test_local_to_global_unnamed_2(self):
        self.check_clang_delta('local-to-global/unnamed_2.c', '--transformation=local-to-global --counter=1')

    def test_local_to_global_unnamed_3(self):
        self.check_clang_delta('local-to-global/unnamed_3.c', '--transformation=local-to-global --counter=2')

    def test_param_to_global_macro(self):
        self.check_clang_delta('param-to-global/macro.c', '--transformation=param-to-global --counter=1')

    def test_reduce_array_dim_non_type_temp_arg(self):
        self.check_clang_delta('reduce-array-dim/non-type-temp-arg.cpp', '--transformation=reduce-array-dim --counter=1')

    def test_reduce_pointer_level_scalar_init_expr(self):
        self.check_clang_delta('reduce-pointer-level/scalar-init-expr.cpp', '--transformation=reduce-pointer-level --counter=1')

    def test_remove_enum_member_value_builtin_macro(self):
        self.check_clang_delta('remove-enum-member-value/builtin_macro.c', '--transformation=remove-enum-member-value --counter=1')

    def test_remove_unused_enum_member_value_range(self):
        self.check_clang_delta('remove-unused-enum-member/range.c', '--transformation=remove-unused-enum-member --counter=4 --to-counter=9')

    def test_remove_namespace_macro(self):
        self.check_clang_delta('remove-namespace/macro.cpp', '--transformation=remove-namespace --counter=1')
        self.check_clang_delta('remove-namespace/macro.cpp', '--transformation=remove-namespace --counter=2',
                               'remove-namespace/macro.output2')
        self.check_clang_delta('remove-namespace/macro.cpp', '--transformation=remove-namespace --counter=3',
                               'remove-namespace/macro.output3')
        self.check_clang_delta('remove-namespace/macro.cpp', '--transformation=remove-namespace --counter=4',
                               'remove-namespace/macro.output4')
        self.check_clang_delta('remove-namespace/macro.cpp', '--transformation=remove-namespace --counter=5',
                               'remove-namespace/macro.output5')

    def test_remove_namespace(self):
        self.check_clang_delta('remove-namespace/namespace.cpp', '--transformation=remove-namespace --counter=1')
        self.check_clang_delta('remove-namespace/namespace.cpp', '--transformation=remove-namespace --counter=2',
                               'remove-namespace/namespace.output2')
        self.check_clang_delta('remove-namespace/namespace.cpp', '--transformation=remove-namespace --counter=3',
                               'remove-namespace/namespace.output3')

    def test_remove_namespace2(self):
        self.check_clang_delta('remove-namespace/namespace2.cpp', '--transformation=remove-namespace --counter=1')
        self.check_clang_delta('remove-namespace/namespace2.cpp', '--transformation=remove-namespace --counter=2',
                               'remove-namespace/namespace2.output2')

    def test_remove_namespace3(self):
        self.check_clang_delta('remove-namespace/namespace3.cpp', '--transformation=remove-namespace --counter=1')
        self.check_clang_delta('remove-namespace/namespace3.cpp', '--transformation=remove-namespace --counter=2',
                               'remove-namespace/namespace3.output2')
        self.check_clang_delta('remove-namespace/namespace3.cpp', '--transformation=remove-namespace --counter=3',
                               'remove-namespace/namespace3.output3')

    def test_remove_namespace4(self):
        self.check_clang_delta('remove-namespace/namespace4.cpp', '--transformation=remove-namespace --counter=1')

    def test_remove_namespace5(self):
        self.check_clang_delta('remove-namespace/namespace5.cpp', '--transformation=remove-namespace --counter=1')
        self.check_clang_delta('remove-namespace/namespace5.cpp', '--transformation=remove-namespace --counter=2',
                               'remove-namespace/namespace5.output2')
        self.check_clang_delta('remove-namespace/namespace5.cpp', '--transformation=remove-namespace --counter=3',
                               'remove-namespace/namespace5.output3')
        self.check_clang_delta('remove-namespace/namespace5.cpp', '--transformation=remove-namespace --counter=4',
                               'remove-namespace/namespace5.output4')

    def test_remove_namespace6(self):
        self.check_clang_delta('remove-namespace/namespace6.cpp', '--transformation=remove-namespace --counter=1')
        self.check_clang_delta('remove-namespace/namespace6.cpp', '--transformation=remove-namespace --counter=2',
                               'remove-namespace/namespace6.output2')

    def test_remove_namespace7(self):
        self.check_clang_delta('remove-namespace/namespace7.cpp', '--transformation=remove-namespace --counter=1')
        self.check_clang_delta('remove-namespace/namespace7.cpp', '--transformation=remove-namespace --counter=2',
                               'remove-namespace/namespace7.output2')
        self.check_clang_delta('remove-namespace/namespace7.cpp', '--transformation=remove-namespace --counter=3',
                               'remove-namespace/namespace7.output3')

    def test_remove_namespace8(self):
        self.check_clang_delta('remove-namespace/namespace8.cpp', '--transformation=remove-namespace --counter=1')
        self.check_clang_delta('remove-namespace/namespace8.cpp', '--transformation=remove-namespace --counter=2',
                               'remove-namespace/namespace8.output2')

    def test_remove_namespace9(self):
        self.check_clang_delta('remove-namespace/namespace9.cpp', '--transformation=remove-namespace --counter=1')

    def test_remove_namespace10(self):
        self.check_clang_delta('remove-namespace/namespace10.cpp', '--transformation=remove-namespace --counter=1')
        self.check_clang_delta('remove-namespace/namespace10.cpp', '--transformation=remove-namespace --counter=2',
                               'remove-namespace/namespace10.output2')

    def test_remove_namespace11(self):
        self.check_clang_delta('remove-namespace/namespace11.cpp', '--transformation=remove-namespace --counter=1')
        self.check_clang_delta('remove-namespace/namespace11.cpp', '--transformation=remove-namespace --counter=2',
                               'remove-namespace/namespace11.output2')

    def test_remove_namespace12(self):
        self.check_clang_delta('remove-namespace/namespace12.cpp', '--transformation=remove-namespace --counter=1')
        self.check_clang_delta('remove-namespace/namespace12.cpp', '--transformation=remove-namespace --counter=2',
                               'remove-namespace/namespace12.output2')
        self.check_clang_delta('remove-namespace/namespace12.cpp', '--transformation=remove-namespace --counter=3',
                               'remove-namespace/namespace12.output3')

    def test_remove_namespace13(self):
        self.check_clang_delta('remove-namespace/namespace13.cpp', '--transformation=remove-namespace --counter=1')
        self.check_clang_delta('remove-namespace/namespace13.cpp', '--transformation=remove-namespace --counter=2',
                               'remove-namespace/namespace13.output2')

    def test_remove_namespace14(self):
        self.check_clang_delta('remove-namespace/namespace14.cpp', '--transformation=remove-namespace --counter=1')

    def test_remove_namespace15(self):
        self.check_clang_delta('remove-namespace/namespace15.cpp', '--transformation=remove-namespace --counter=1')
        self.check_clang_delta('remove-namespace/namespace15.cpp', '--transformation=remove-namespace --counter=2',
                               'remove-namespace/namespace15.output2')
        self.check_clang_delta('remove-namespace/namespace15.cpp', '--transformation=remove-namespace --counter=3',
                               'remove-namespace/namespace15.output3')

    def test_remove_nested_function_remove_nested_func1(self):
        self.check_clang_delta('remove-nested-function/remove_nested_func1.cc', '--transformation=remove-nested-function --counter=1')

    def test_remove_try_catch_1(self):
        self.check_clang_delta('remove-try-catch/try-catch-1.cpp', '--transformation=remove-try-catch --counter=1')

    def test_remove_try_catch_2(self):
        self.check_clang_delta('remove-try-catch/try-catch-2.cpp', '--transformation=remove-try-catch --counter=2')

    def test_remove_unused_field_designated1(self):
        self.check_clang_delta('remove-unused-field/designated1.c', '--transformation=remove-unused-field --counter=1')

    def test_remove_unused_field_designated2(self):
        self.check_clang_delta('remove-unused-field/designated2.c', '--transformation=remove-unused-field --counter=2')

    def test_remove_unused_field_designated3(self):
        self.check_clang_delta('remove-unused-field/designated3.c', '--transformation=remove-unused-field --counter=3')

    def test_remove_unused_field_designated4(self):
        self.check_clang_delta('remove-unused-field/designated4.c', '--transformation=remove-unused-field --counter=1')

    def test_remove_unused_field_designated5(self):
        self.check_clang_delta('remove-unused-field/designated5.c', '--transformation=remove-unused-field --counter=2')

    def test_remove_unused_field_unused_field1(self):
        self.check_clang_delta('remove-unused-field/unused_field1.c', '--transformation=remove-unused-field --counter=1')

    def test_remove_unused_field_unused_field2(self):
        self.check_clang_delta('remove-unused-field/unused_field2.c', '--transformation=remove-unused-field --counter=2')

    def test_remove_unused_field_unused_field3(self):
        self.check_clang_delta('remove-unused-field/unused_field3.cpp', '--transformation=remove-unused-field --counter=1')

    def test_remove_unused_function_class(self):
        self.check_clang_delta('remove-unused-function/class.cc', '--transformation=remove-unused-function --counter=1')

    def test_remove_unused_function_const(self):
        self.check_clang_delta('remove-unused-function/const.cc', '--transformation=remove-unused-function --counter=1')
        self.check_clang_delta('remove-unused-function/const.cc', '--transformation=remove-unused-function --counter=2',
                               'remove-unused-function/const.output2')

    def test_remove_unused_function_default(self):
        self.check_clang_delta('remove-unused-function/default.cc', '--transformation=remove-unused-function --counter=1')
        self.check_clang_delta('remove-unused-function/default.cc', '--transformation=remove-unused-function --counter=2',
                               'remove-unused-function/default.output2')

    def test_remove_unused_function_delete(self):
        self.check_clang_delta('remove-unused-function/delete.cc', '--transformation=remove-unused-function --counter=1')

    def test_remove_unused_function_delete2(self):
        self.check_clang_delta('remove-unused-function/delete2.cc', '--transformation=remove-unused-function --counter=1')
        self.check_clang_delta('remove-unused-function/delete2.cc', '--transformation=remove-unused-function --counter=2',
                               'remove-unused-function/delete2.output2')
        self.check_clang_delta('remove-unused-function/delete2.cc', '--transformation=remove-unused-function --counter=3',
                               'remove-unused-function/delete2.output3')
        self.check_clang_delta('remove-unused-function/delete2.cc', '--transformation=remove-unused-function --counter=4',
                               'remove-unused-function/delete2.output4')

    def test_remove_unused_function_inline_ns(self):
        self.check_query_instances('remove-unused-function/inline_ns.cc', '--query-instances=remove-unused-function',
                                   'Available transformation instances: 0')

    def test_remove_unused_function_macro1(self):
        self.check_clang_delta('remove-unused-function/macro1.cc', '--transformation=remove-unused-function --counter=1')

    def test_remove_unused_function_macro2(self):
        self.check_clang_delta('remove-unused-function/macro2.cc', '--transformation=remove-unused-function --counter=1')

    def test_remove_unused_function_macro3(self):
        self.check_clang_delta('remove-unused-function/macro3.cc', '--transformation=remove-unused-function --counter=1')

    def test_remove_unused_function_template1(self):
        self.check_clang_delta('remove-unused-function/template1.cc', '--transformation=remove-unused-function --counter=1')

    def test_remove_unused_function_template2(self):
        self.check_clang_delta('remove-unused-function/template2.cc', '--transformation=remove-unused-function --counter=1')

    def test_remove_unused_function_unused_funcs(self):
        self.check_clang_delta('remove-unused-function/unused-funcs.cc', '--transformation=remove-unused-function --counter=1')

    def test_remove_unused_var_struct1(self):
        self.check_clang_delta('remove-unused-var/struct1.c', '--transformation=remove-unused-var --counter=1')

    def test_remove_unused_var_struct2(self):
        self.check_clang_delta('remove-unused-var/struct2.c', '--transformation=remove-unused-var --counter=1')

    def test_remove_unused_var_unused_var(self):
        self.check_clang_delta('remove-unused-var/unused_var.cpp', '--transformation=remove-unused-var --counter=1')

    def test_rename_class_base_specifier(self):
        self.check_clang_delta('rename-class/base_specifier.cpp', '--transformation=rename-class --counter=1')

    def test_rename_class_bool(self):
        self.check_clang_delta('rename-class/bool.cc', '--transformation=rename-class --counter=1')

    def test_rename_class_class_template(self):
        self.check_clang_delta('rename-class/class_template.cc', '--transformation=rename-class --counter=1')

    def test_rename_class_class_template2(self):
        self.check_clang_delta('rename-class/class_template2.cc', '--transformation=rename-class --counter=1')

    def test_rename_class_dependent(self):
        self.check_clang_delta('rename-class/dependent.cpp', '--transformation=rename-class --counter=1')

    def test_rename_class_dependent_name(self):
        self.check_clang_delta('rename-class/dependent_name.cpp', '--transformation=rename-class --counter=1')

    def test_rename_class_derive(self):
        self.check_clang_delta('rename-class/derive.cc', '--transformation=rename-class --counter=1')

    def test_rename_class_dtor(self):
        self.check_clang_delta('rename-class/dtor.cc', '--transformation=rename-class --counter=1')

    def test_rename_class_dtor1(self):
        self.check_clang_delta('rename-class/dtor1.cc', '--transformation=rename-class --counter=1')

    def test_rename_class_elaborated_type1(self):
        self.check_clang_delta('rename-class/elaborated_type1.cpp', '--transformation=rename-class --counter=1')

    def test_rename_class_elaborated_type2(self):
        self.check_clang_delta('rename-class/elaborated_type2.cpp', '--transformation=rename-class --counter=1')

    def test_rename_class_explicit_specialization(self):
        self.check_clang_delta('rename-class/explicit_specialization.cpp', '--transformation=rename-class --counter=1')

    def test_rename_class_forward_decl(self):
        self.check_clang_delta('rename-class/forward_decl.cc', '--transformation=rename-class --counter=1')

    def test_rename_class_injected_name(self):
        self.check_clang_delta('rename-class/injected_name.cpp', '--transformation=rename-class --counter=1')

    def test_rename_class_instantiation(self):
        self.check_clang_delta('rename-class/instantiation.cpp', '--transformation=rename-class --counter=1')

    def test_rename_class_parm(self):
        self.check_clang_delta('rename-class/parm.cpp', '--transformation=rename-class --counter=1')

    def test_rename_class_partial_specialization(self):
        self.check_clang_delta('rename-class/partial_specialization.cpp', '--transformation=rename-class --counter=1')

    def test_rename_class_rename_class1(self):
        self.check_clang_delta('rename-class/rename-class1.cpp', '--transformation=rename-class --counter=1')

    def test_rename_class_rename_class2(self):
        self.check_clang_delta('rename-class/rename-class2.cpp', '--transformation=rename-class --counter=1')

    def test_rename_class_specialization(self):
        self.check_clang_delta('rename-class/specialization.cpp', '--transformation=rename-class --counter=1')

    def test_rename_class_static_member(self):
        self.check_clang_delta('rename-class/static_member.cc', '--transformation=rename-class --counter=1')

    def test_rename_class_template_class_1(self):
        self.check_clang_delta('rename-class/template_class_1.cpp', '--transformation=rename-class --counter=1')

    def test_rename_class_template_parm(self):
        self.check_clang_delta('rename-class/template_parm.cpp', '--transformation=rename-class --counter=1')

    def test_rename_class_template_template(self):
        self.check_clang_delta('rename-class/template_template.cpp', '--transformation=rename-class --counter=1')

    def test_rename_class_template_template_parm(self):
        self.check_clang_delta('rename-class/template_template_parm.cpp', '--transformation=rename-class --counter=1')

    def test_rename_class_typedef(self):
        self.check_clang_delta('rename-class/typedef.cpp', '--transformation=rename-class --counter=1')

    def test_rename_class_typedef2(self):
        self.check_clang_delta('rename-class/typedef2.cc', '--transformation=rename-class --counter=1')

    def test_rename_class_using(self):
        self.check_clang_delta('rename-class/using.cpp', '--transformation=rename-class --counter=1')

    def test_rename_class_using1(self):
        self.check_clang_delta('rename-class/using1.cc', '--transformation=rename-class --counter=1')

    def test_rename_cxx_method_overloaded(self):
        self.check_clang_delta('rename-cxx-method/overloaded.cc', '--transformation=rename-cxx-method --counter=1')

    def test_rename_cxx_method_test1(self):
        self.check_clang_delta('rename-cxx-method/test1.cc', '--transformation=rename-cxx-method --counter=1')

    def test_rename_cxx_method_test2(self):
        self.check_clang_delta('rename-cxx-method/test2.cc', '--transformation=rename-cxx-method --counter=1')

    def test_rename_cxx_method_test3(self):
        self.check_clang_delta('rename-cxx-method/test3.cc', '--transformation=rename-cxx-method --counter=1')

    def test_rename_fun_templ(self):
        self.check_clang_delta('rename-fun/func_templ.cc', '--transformation=rename-fun --counter=1')

    def test_rename_fun_multi(self):
        self.check_clang_delta('rename-fun/multi.c', '--transformation=rename-fun --counter=1')

    def test_rename_fun_overloaded(self):
        self.check_clang_delta('rename-fun/overloaded.cc', '--transformation=rename-fun --counter=1')

    def test_rename_fun_test1(self):
        self.check_clang_delta('rename-fun/test1.c', '--transformation=rename-fun --counter=1')

    def test_rename_param_invalid(self):
        self.check_clang_delta('rename-param/invalid.c', '--transformation=rename-param --counter=1')

    def test_rename_param_stuck(self):
        self.check_error_message('rename-param/stuck.ii', '--transformation=rename-param --counter=1', 'Error: No modification to the transformed program!')

    def test_rename_var_rename_var(self):
        self.check_clang_delta('rename-var/rename-var.c', '--transformation=rename-var --counter=1')

    def test_replace_derived_class_replace_derived1(self):
        self.check_clang_delta('replace-derived-class/replace-derived1.cpp', '--transformation=replace-derived-class --counter=1')

    def test_replace_derived_class_replace_derived2(self):
        self.check_clang_delta('replace-derived-class/replace-derived2.cpp', '--transformation=replace-derived-class --counter=1')

    def test_replace_derived_class_replace_derived3(self):
        self.check_clang_delta('replace-derived-class/replace-derived3.cpp', '--transformation=replace-derived-class --counter=1')

    def test_replace_derived_class_replace_derived4(self):
        self.check_clang_delta('replace-derived-class/replace-derived4.cpp', '--transformation=replace-derived-class --counter=1')

    def test_replace_function_def_with_decl_macro1(self):
        self.check_clang_delta('replace-function-def-with-decl/macro1.c', '--transformation=replace-function-def-with-decl --counter=1 --to-counter=2')

    def test_replace_function_def_with_decl_macro2(self):
        self.check_clang_delta('replace-function-def-with-decl/macro2.c', '--transformation=replace-function-def-with-decl --counter=1 --to-counter=2')

    def test_replace_function_def_with_decl_simple_preserve_missing(self):
        self.check_clang_delta('replace-function-def-with-decl/simple.cpp',
                               '--transformation=replace-function-def-with-decl --preserve-routine=blahblahblah --counter=1 --to-counter=3',
                               output_file='replace-function-def-with-decl/simple.cpp.preserve_missing.output')

    def test_replace_function_def_with_decl_simple_preserve_quack(self):
        self.check_clang_delta('replace-function-def-with-decl/simple.cpp',
                               '--transformation=replace-function-def-with-decl --preserve-routine=quack --counter=1 --to-counter=2',
                               output_file='replace-function-def-with-decl/simple.cpp.preserve_quack.output')

    def test_replace_function_def_with_decl_simple_preserve_foo(self):
        self.check_clang_delta('replace-function-def-with-decl/simple.cpp',
                               '--transformation=replace-function-def-with-decl --preserve-routine=Moo::foo --counter=1 --to-counter=9999 --warn-on-counter-out-of-bounds',
                               output_file='replace-function-def-with-decl/simple.cpp.preserve_foo.output')

    def test_return_void_test1(self):
        self.check_clang_delta('return-void/test1.c', '--transformation=return-void --counter=1')

    def test_return_void_test2(self):
        self.check_clang_delta('return-void/test2.c', '--transformation=return-void --counter=1')

    def test_return_void_test3(self):
        self.check_clang_delta('return-void/test3.c', '--transformation=return-void --counter=1')

    def test_return_void_test4(self):
        self.check_clang_delta('return-void/test4.c', '--transformation=return-void --counter=1')

    def test_return_void_test5(self):
        self.check_clang_delta('return-void/test5.c', '--transformation=return-void --counter=1')

    def test_return_void_test6(self):
        self.check_clang_delta('return-void/test6.c', '--transformation=return-void --counter=1')

    def test_return_void_test7(self):
        self.check_clang_delta('return-void/test7.cc', '--transformation=return-void --counter=1')

    def test_simplify_callexpr_macro(self):
        self.check_clang_delta('simplify-callexpr/macro.c', '--transformation=simplify-callexpr --counter=1')

    def test_simplify_callexpr_test(self):
        self.check_clang_delta('simplify-callexpr/test.c', '--transformation=simplify-callexpr --counter=1')

    def test_simplify_callexpr_test2(self):
        self.check_clang_delta('simplify-callexpr/test2.c', '--transformation=simplify-callexpr --counter=1')

    def test_simplify_if_macro(self):
        self.check_clang_delta('simplify-if/macro.c', '--transformation=simplify-if --counter=1')

    def test_simplify_simple_recursive_template(self):
        self.check_clang_delta('simplify-recursive-template-instantiation/test.cc', '--transformation=simplify-recursive-template-instantiation --counter=1')

    def test_template_arg_to_int_not_valid_5(self):
        self.check_query_instances('template-arg-to-int/not_valid5.cc', '--query-instances=template-arg-to-int',
                                   'Available transformation instances: 0')

    def test_union_to_struct_union1(self):
        self.check_clang_delta('union-to-struct/union1.c', '--transformation=union-to-struct --counter=1')

    def test_union_to_struct_union2(self):
        self.check_clang_delta('union-to-struct/union2.c', '--transformation=union-to-struct --counter=1')

    def test_union_to_struct_union3(self):
        self.check_clang_delta('union-to-struct/union3.c', '--transformation=union-to-struct --counter=1')

    def test_piggypacking(self):
        current = os.path.dirname(__file__)
        binary = os.path.join(current, '../clang_delta')
        cmd = '%s %s %s' % (binary, os.path.join(current, 'remove-unused-function/macro2.cc'),
                            '--transformation=remove-unused-function --counter=111 --to-counter=222 --warn-on-counter-out-of-bounds --report-instances-count')
        run = subprocess.run(cmd, shell=True, encoding='utf8', stderr=subprocess.PIPE, stdout=subprocess.PIPE)
        assert 'Available transformation instances: 1' in run.stderr
        assert 'Warning: number of transformation instances exceeded' in run.stderr

    def test_simple_inliner_alias(self):
        self.check_clang_delta('simple-inliner/alias-crash.c', '--transformation=simple-inliner --counter=1')

    def test_class_to_struct(self):
        self.check_clang_delta('class-to-struct/class-to-struct1.C', '--transformation=class-to-struct --counter=1')

    def test_class_to_struct_forward(self):
        self.check_query_instances('class-to-struct/class-to-struct-forward.C', '--query-instances=class-to-struct',
                                   'Available transformation instances: 0')

    def test_class_template_to_class(self):
        self.check_clang_delta('class-template-to-class/test1.cc', '--transformation=class-template-to-class --counter=1')

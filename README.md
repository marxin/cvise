# C-Vise

[![Travis Build Status](https://travis-ci.com/marxin/cvise.svg?branch=master)](https://travis-ci.com/marxin/cvise)

## About 

C-Vise is a super-parallel Python port of the [C-Reduce](https://github.com/csmith-project/creduce/).
The port is fully compatible to the C-Reduce and uses the same efficient
LLVM-based C/C++ reduction tool named `clang_delta`.

C-Vise is a tool that takes a large C, C++ or OpenCL program that
has a property of interest (such as triggering a compiler bug) and
automatically produces a much smaller C/C++ or OpenCL program that has
the same property.  It is intended for use by people who discover and
report bugs in compilers and other tools that process C/C++ or OpenCL
code.

*NOTE:* C-Vise happens to do a pretty good job reducing the size of
programs in languages other than C/C++, such as JavaScript and Rust.
If you need to reduce programs in some other language, please give it
a try.

## Installation

See [INSTALL.md](INSTALL.md).

## Usage example

The C-Vise can be used for a reduction of a compiler crash. In this case,
let's consider an existing [PR9453](https://gcc.gnu.org/bugzilla/show_bug.cgi?id=94534):

Original test-case (`pr94534.C` file):
```c++
template<typename T>
class Demo
{
  struct
  {
    Demo* p;
  } payload{this};
  friend decltype(payload);
};

int main()
{
  Demo<int> d;
}
```

The program crashes in GCC, but is accepted with Clang:
```
$ g++ pr94534.C -c
pr94534.C: In instantiation of ‘class Demo<int>’:
pr94534.C:13:13:   required from here
pr94534.C:7:5: internal compiler error: Segmentation fault
    7 |   } payload{this};
      |     ^~~~~~~
0x10a1d8f crash_signal
	/home/marxin/Programming/gcc/gcc/toplev.c:328
0x7ffff78fef1f ???
	/usr/src/debug/glibc-2.31-4.1.x86_64/signal/../sysdeps/unix/sysv/linux/x86_64/sigaction.c:0
0xae31a8 instantiate_class_template_1
	/home/marxin/Programming/gcc/gcc/cp/pt.c:11973
...
$ clang++ pr94534.C -c
```

So let's build a reduction script so that it will grep for `instantiate_class_template_1`
on the standard error output and that it compiles with Clang:

`reduce-ice.sh`:
```shell
#!/bin/sh
g++ pr94534.C -c 2>&1 | grep 'instantiate_class_template_1' && clang++ -c pr94534.C
```

The reduction can be then run with:
```shell
$ cvise ./reduce-ice.sh pr94534.C
INFO ===< 30356 >===
INFO running 16 interestingness tests in parallel
INFO INITIAL PASSES
INFO ===< IncludesPass >===
...
template <typename> class a {
  int b;
  friend decltype(b);
};
void c() { a<int> d; }
```

## Notes

1. When set to use more than one core, C-Vise can cause space in
`/tmp` to be leaked. This happens because sometimes C-Vise will kill
a compiler invocation when a result that is computed in parallel makes
it clear that that compiler invocation is no longer useful. If the
compiler leaves files in `/tmp` when it is killed, C-Vise has no way
to discover and remove the files. You will need to do this manually
from time to time if temporary file space is limited. The leakage is
typically pretty slow. If you need to avoid this problem altogether,
you can run C-Vise on a single core (using `--n 1`) in which case
C-Vise will never kill a running compiler instance. Alternatively, a
command line option such as `-pipe` (supported by GCC) may suppress
the creation of temporary files altogether. Another possibility is to
set the `TMPDIR` environment variable to something like
`/tmp/cvise-stuff` before invoking C-Vise -- assuming that the
tools you are invoking respect this variable.

2. Each invocation of the interestingness test is performed in a fresh
temporary directory containing a copy of the file that is being
reduced. If your interestingness test requires access to other files,
you should either copy them into the current working directory or else
refer to them using an absolute path.

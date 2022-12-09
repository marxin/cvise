# C-Vise

[![Build](https://github.com/marxin/cvise/actions/workflows/build.yml/badge.svg)](https://github.com/marxin/cvise/actions/workflows/build.yml)
[![Build LLVM nightly](https://github.com/marxin/cvise/actions/workflows/build-llvm-nightly.yml/badge.svg)](https://github.com/marxin/cvise/actions/workflows/build-llvm-nightly.yml)

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

The project also contains a simple wrapper `cvise-delta` which simulates
the same behavior as original [delta](http://delta.tigris.org/) tool
(but in super-parallel way).

*NOTE*: C-Vise happens to do a pretty good job reducing the size of
programs in languages other than C/C++, such as JavaScript and Rust.
If you need to reduce programs in some other language, please give it
a try.

*NOTE*: Binary pass group (`--pass-group=binary`) contains an experimental pass
that can reduce GCC's `.gcda` files.

## Speed Comparison

I made a comparison for couple of GCC bug reports on my AMD Ryzen 7 2700X Eight-Core Processor
machine with the following results:

| Test-case | Size | C-Vise Reduction | C-Reduce Reduction | Speed Up |
| --- | --- | --- | --- | --- |
| [PR92516](http://gcc.gnu.org/PR92516) | 6.5 MB | 35m | 77m | 220% |
| [PR94523](http://gcc.gnu.org/PR94523) | 2.1 MB | 15m | 33m | 220% |
| [PR94632](http://gcc.gnu.org/PR94632) | 3.3 MB | 20m | 28m | 40% |
| [PR94937](http://gcc.gnu.org/PR94937) | 8.5 MB | 242m | 303m | 125% |

## Installation

See [INSTALL.md](INSTALL.md).

## Usage example

The C-Vise can be used for a reduction of a compiler crash. In this case,
let's consider an existing [PR94534](https://gcc.gnu.org/bugzilla/show_bug.cgi?id=94534):

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
```console
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
```console
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

1. C-Vise creates temporary directories in `$TMPDIR` and so usage
of a `tmpfs` directory is recommended.

1. Each invocation of the interestingness test is performed in a fresh
temporary directory containing a copy of the file that is being
reduced. If your interestingness test requires access to other files,
you should either copy them into the current working directory or else
refer to them using an absolute path.

1. If you copy the compiler invocation line from your build tool, remove
-Werror if present. Some C-Vise passes introduce warnings, so -Werror
will make those passes ineffective.

   Doing that, a reduction will typically end up faster, however,
   one may end up with a code snippet full of warnings that needs
   to be addresses after the reduction.

1. Adding `-Wfatal-errors` to the interestingness test can speed up
   large reductions by causing the compiler to bail out quickly on errors,
   rather than trying to soldier on producing a result that is eventually
   discarded.

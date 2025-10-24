# Installing C-Vise

## Using a Package Manager

Before compiling C-Vise yourself, you might want to see if your OS
comes with a pre-compiled package for C-Vise.

[![Packaging status](https://repology.org/badge/vertical-allrepos/cvise.svg)](https://repology.org/project/cvise/versions)

### openSUSE Tumbleweed

```shell
zypper in cvise
```

### Ubuntu

```shell
apt-get install cvise
```

### Gentoo Linux

```shell
emerge cvise
```

### Fedora
```shell
yum install cvise
```

### Debian bullseye
```shell
apt install cvise
```

### Using Docker (or Podman)

```shell
$ podman run -it opensuse/tumbleweed bash
714d543633e1 $ zypper -n install cvise
714d543633e1 $ cvise --version
cvise 1.2.0
```

## From Source

### Prereqs

C-Vise is written in Python 3, C++, and C.  To compile and run C-Vise,
you will need a development environment that supports these languages.
C-Vise's build system requires CMake.

Beyond the basic compile/build tools, C-Vise depends on a set of
third-party software packages, including LLVM.

On Ubuntu or Mint, the prerequisites other than LLVM can be installed
like this:

```
sudo apt-get install \
  flex build-essential unifdef
```

On FreeBSD 12.1, the prerequisites can be installed like this:

```
sudo pkg install \
  llvm90 flex
```

Otherwise, install these packages either manually or using the package
manager:

* [Flex](http://flex.sourceforge.net/)

* [LLVM/Clang 18.0.0 or later](http://llvm.org/releases/download.html)
  (No need to compile it: the appropriate "pre-built binaries" package is
  all you need).  For example, the openSUSE Tumbleweed provides them
  by `llvm-devel` and `clang-devel` packages.

  Tested LLVM versions: ``18.0.0`` - ``22.0.0``

* [Python 3.9+](https://www.python.org/downloads/)

* [Pebble](https://pypi.org/project/Pebble/)

* [chardet](https://pypi.org/project/chardet/)

* [msgspec](https://pypi.org/project/msgspec/)

* [psutil](https://pypi.org/project/psutil/)

* [zstandard](https://pypi.org/project/zstandard/)

* [CMake](https://cmake.org/)

* [unifdef](http://dotat.at/prog/unifdef/)

Optional packages:

* [pytest](https://docs.pytest.org/en/latest/)

* [pytest-mock](https://pypi.org/project/pytest-mock/)

* [pytest-subprocess](https://pypi.org/project/pytest-subprocess/)

* [pytest-xdist](https://pypi.org/project/pytest-xdist/)

* [colordiff](https://www.colordiff.org/)

* [jsonschema](https://pypi.org/project/jsonschema/)

## Building and installing C-Vise

You can configure, build, and install C-Vise with the CMake.

From either the source directory or a build directory:

```
cmake [source-dir] [options]
make
make install
```

If LLVM/Clang is not in your search path, you can tell CMake where to
find LLVM/Clang:

```
# Use the LLVM/Clang tree rooted at /opt/llvm
cmake [source-dir] -DCMAKE_PREFIX_PATH=/opt/llvm
```

Alternatively, if you choose to build LLVM and Clang yourself, you can
set the `LLVM_DIR` and/or `Clang_DIR` variables to paths where CMake can
find the `LLVMConfig.cmake` and/or `ClangConfig.cmake` files.  The
value of `LLVM_DIR` is usually `./lib/cmake/llvm`, relative to your LLVM
build or install directory.  Similarly, the value of `Clang_DIR` is
usually `./lib/cmake/clang`, relative to your Clang build or install
directory.  For example:

```
# Use separate LLVM and Clang build trees, /work/my-{llvm,clang}
cmake [source-dir] -DLLVM_DIR=/work/my-llvm/lib/cmake/llvm \
  -DClang_DIR=/work/my-clang/lib/cmake/clang
```

You do *not* need to set `Clang_DIR` if you build Clang within your LLVM
tree.  Also, note that you must actually *build* LLVM and Clang before
building C-Vise.

Note that assertions are enabled by default. To disable assertions:

```
cmake ... -DENABLE_TRANS_ASSERT=OFF
```

## Building on windows

Build LLVM according to https://llvm.org/docs/GettingStarted.html#getting-the-source-code-and-building-llvm
I used these LLVM build options:
```
@call "%PROGRAMFILES(x86)%\Microsoft Visual Studio\2019\Enterprise\VC\Auxiliary\Build\vcvarsall.bat" x86_amd64
mkdir build
cd build
"C:\Program Files (x86)\Microsoft Visual Studio\2019\Enterprise\Common7\IDE\CommonExtensions\Microsoft\CMake\CMake\bin\cmake.exe" -S ..\llvm -DLLVM_ENABLE_PROJECTS=clang -DLLVM_TARGETS_TO_BUILD=X86 -DCMAKE_BUILD_TYPE=Release -Thost=x64
msbuild ALL_BUILD.vcxproj /p:Configuration=Release /p:Platform=x64 /p:VisualStudioVersion=16.0 /v:m
```

Download flex from https://github.com/lexxmark/winflexbison/releases/download/v2.5.24/win_flex_bison-2.5.24.zip

```
pip install pytest psutil pebble chardet
@call "%PROGRAMFILES(x86)%\Microsoft Visual Studio\2019\Enterprise\VC\Auxiliary\Build\vcvarsall.bat" x86_amd64
set LLVM_DIR=D:\src\llvm-project\build\lib\cmake\llvm
set CLANG_DIR=D:\src\llvm-project\build\lib\cmake\clang
"C:\Program Files (x86)\Microsoft Visual Studio\2019\Enterprise\Common7\IDE\CommonExtensions\Microsoft\CMake\CMake\bin\cmake.exe"  -A x64 -Thost=x64  c:\src\cvise -DCMAKE_INSTALL_PREFIX=c:\tools\cvise\
msbuild INSTALL.vcxproj /p:Configuration=Release /p:Platform=x64 /p:VisualStudioVersion=16.0 /v:m
```

Run with: `python C:\tools\cvise\bin\cvise`

## Testing

You can test the project with:

```
make test
```

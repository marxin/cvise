cmake_minimum_required(VERSION 3.14)
project(clang_include_graph)

# find_package(LLVM) is done by the topmost "CMakeLists.txt" file.
# find_package(Clang) is done by the topmost "CMakeLists.txt" file.

include_directories(${LLVM_INCLUDE_DIRS})
include_directories(${CLANG_INCLUDE_DIRS})

set(LLVM_LINK_COMPONENTS
  Support
  )

add_executable(clang_include_graph
  Main.cpp
  )

if (${LLVM_LINK_LLVM_DYLIB})
  set(CLANG_LIBS
    clang-cpp
    LLVM
  )
else()
  set(CLANG_LIBS
    clangBasic
    clangFrontend
    clangLex
    clangTooling
  )
endif()
target_link_libraries(clang_include_graph ${CLANG_LIBS})
cvise_fix_dia_sdk(clang_include_graph)

install(TARGETS clang_include_graph
  DESTINATION "${CMAKE_INSTALL_LIBEXECDIR}/${cvise_PACKAGE}/"
  )

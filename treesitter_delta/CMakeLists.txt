## -*- mode: CMake -*-

cmake_minimum_required(VERSION 3.14)

project(treesitter_delta)

add_executable(treesitter_delta
    EraseNamespace.cpp
    RemoveFunction.cpp
    Main.cpp
    ReplaceFunctionDefWithDecl.cpp
    TreeSitterUtils.cpp
)
target_link_libraries(treesitter_delta
    tree-sitter
    tree-sitter-cpp
)

install(TARGETS treesitter_delta
  DESTINATION "${CMAKE_INSTALL_LIBEXECDIR}/${cvise_PACKAGE}/"
  )

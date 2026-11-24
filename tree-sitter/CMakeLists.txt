## -*- mode: CMake -*-

cmake_minimum_required(VERSION 3.14)

project(tree-sitter)

add_library(tree-sitter STATIC lib/src/lib.c)
target_include_directories(tree-sitter
  PRIVATE lib/src
  PUBLIC lib/include
)
if(NOT MSVC)
  target_compile_options(tree-sitter PRIVATE -std=gnu99)
endif()

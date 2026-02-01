## -*- mode: CMake -*-
##
## Copyright (c) 2012, 2013, 2014, 2015, 2016 The University of Utah
## All rights reserved.
##
## This file is distributed under the University of Illinois Open Source
## License.  See the file COPYING for details.

###############################################################################

cmake_minimum_required(VERSION 3.14)

# find_package(FLEX) is done by the topmost "CMakeLists.txt" file.

if(CMAKE_CXX_COMPILER_ID STREQUAL "GNU"
    OR CMAKE_CXX_COMPILER_ID MATCHES "Clang")
  set(CMAKE_C_FLAGS "${CMAKE_C_FLAGS} -pedantic")
  set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -pedantic")
endif()

# Some versions of Flex (e.g., the macOS-provided one) define "yyleng" as being
# of the "yy_size_t" type, which is size_t by default; override it to int to be
# compatible with other versions.
set(CMAKE_C_FLAGS "${CMAKE_C_FLAGS} -Dyy_size_t=int -DYY_TYPEDEF_YY_SIZE_T")
set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -Dyy_size_t=int -DYY_TYPEDEF_YY_SIZE_T")

###############################################################################

project(clex)

include_directories(${PROJECT_BINARY_DIR})
include_directories(${PROJECT_SOURCE_DIR})
include_directories(${CMAKE_BINARY_DIR})

FLEX_TARGET(clex_scanner
  clex.l
  ${PROJECT_BINARY_DIR}/clex.c
  )

add_executable(clex
  ${FLEX_clex_scanner_OUTPUTS}
  defs.h
  driver.c
  )

###############################################################################

project(strlex)
include_directories(${PROJECT_BINARY_DIR})
include_directories(${PROJECT_SOURCE_DIR})
include_directories(${CMAKE_BINARY_DIR})

FLEX_TARGET(strlex_scanner
  strlex.l
  ${PROJECT_BINARY_DIR}/strlex.c
  )

add_executable(strlex
  ${FLEX_strlex_scanner_OUTPUTS}
  defs.h
  driver.c
  )

if(CMAKE_CXX_COMPILER_ID STREQUAL "GNU"
    OR CMAKE_CXX_COMPILER_ID MATCHES "Clang")
set_source_files_properties(clex.c PROPERTIES COMPILE_FLAGS "-Wno-unused-function -Wno-sign-compare")
set_source_files_properties(strlex.c PROPERTIES COMPILE_FLAGS "-Wno-unused-function -Wno-sign-compare")
endif()
if(CMAKE_CXX_COMPILER_ID MATCHES "MSVC")
set_source_files_properties(clex.c PROPERTIES COMPILE_FLAGS -DYY_NO_UNISTD_H)
set_source_files_properties(strlex.c PROPERTIES COMPILE_FLAGS -DYY_NO_UNISTD_H)
endif()

###############################################################################

install(TARGETS clex strlex
  DESTINATION "${CMAKE_INSTALL_LIBEXECDIR}/${cvise_PACKAGE}/"
  )

###############################################################################

## End of file.

## -*- mode: CMake -*-
##
## Copyright (c) 2012, 2013, 2014, 2015, 2016 The University of Utah
## All rights reserved.
##
## This file is distributed under the University of Illinois Open Source
## License.  See the file COPYING for details.

###############################################################################

cmake_minimum_required(VERSION 3.3)

# find_package(FLEX) is done by the topmost "CMakeLists.txt" file.

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
    OR CMAKE_CXX_COMPILER_ID STREQUAL "Clang")
set_source_files_properties(clex.c PROPERTIES COMPILE_FLAGS -Wno-unused-function)
set_source_files_properties(strlex.c PROPERTIES COMPILE_FLAGS -Wno-unused-function)
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

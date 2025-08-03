## -*- mode: CMake -*-
##
## Copyright (c) 2016 The University of Utah
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

###############################################################################

project(topformflat)

include_directories(${PROJECT_BINARY_DIR})
include_directories(${PROJECT_SOURCE_DIR})
include_directories(${CMAKE_BINARY_DIR})

FLEX_TARGET(topformflat_scanner
  topformflat.l
  ${PROJECT_BINARY_DIR}/topformflat.c
  )

add_executable(topformflat_hints
  ${FLEX_topformflat_scanner_OUTPUTS}
  )

if(CMAKE_CXX_COMPILER_ID STREQUAL "GNU"
    OR CMAKE_CXX_COMPILER_ID MATCHES "Clang")
set_source_files_properties(topformflat.c PROPERTIES COMPILE_FLAGS "-Wno-unused-function -Wno-unused-parameter -Wno-sign-compare")
endif()
if(CMAKE_CXX_COMPILER_ID MATCHES "MSVC")
set_source_files_properties(topformflat.c PROPERTIES COMPILE_FLAGS -DYY_NO_UNISTD_H)
endif()

###############################################################################

install(TARGETS topformflat_hints
  DESTINATION "${CMAKE_INSTALL_LIBEXECDIR}/${cvise_PACKAGE}/"
  )

###############################################################################

## End of file.

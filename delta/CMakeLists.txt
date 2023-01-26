## -*- mode: CMake -*-
##
## Copyright (c) 2016 The University of Utah
## All rights reserved.
##
## This file is distributed under the University of Illinois Open Source
## License.  See the file COPYING for details.

###############################################################################

cmake_minimum_required(VERSION 3.3)

# find_package(FLEX) is done by the topmost "CMakeLists.txt" file.

###############################################################################

project(topformflat)

include_directories(${PROJECT_BINARY_DIR})
include_directories(${PROJECT_SOURCE_DIR})
include_directories(${CMAKE_BINARY_DIR})

FLEX_TARGET(topformflat_scanner
  topformflat.l
  ${PROJECT_BINARY_DIR}/topformflat.c
  )

add_executable(topformflat
  ${FLEX_topformflat_scanner_OUTPUTS}
  )

if(CMAKE_CXX_COMPILER_ID STREQUAL "GNU"
    OR CMAKE_CXX_COMPILER_ID STREQUAL "Clang")
set_source_files_properties(topformflat.c PROPERTIES COMPILE_FLAGS "-Wno-unused-function -Wno-unused-parameter")
endif()
if(CMAKE_CXX_COMPILER_ID MATCHES "MSVC")
set_source_files_properties(topformflat.c PROPERTIES COMPILE_FLAGS -DYY_NO_UNISTD_H)
endif()

###############################################################################

install(TARGETS topformflat
  DESTINATION "${CMAKE_INSTALL_LIBEXECDIR}/${cvise_PACKAGE}/"
  )

###############################################################################

## End of file.

## -*- mode: CMake -*-
##
## Copyright (c) 2012, 2013, 2014, 2015, 2016, 2017, 2018, 2019 The University of Utah
## All rights reserved.
##
## This file is distributed under the University of Illinois Open Source
## License.  See the file COPYING for details.

###############################################################################

cmake_minimum_required(VERSION 2.8.12)

list(APPEND CMAKE_MODULE_PATH "${CMAKE_SOURCE_DIR}/cmake")

include(CheckIncludeFile)
include(CheckCXXCompilerFlag)
include(GetGitRevisionDescription)

project(cvise)

if(CMAKE_SOURCE_DIR STREQUAL PROJECT_BINARY_DIR)
  message(FATAL_ERROR "CMAKE_SOURCE_DIR should be different from PROJECT_BINARY_DIR")
endif()

###############################################################################

# Locate LLVM and check its version.  Do this here because we need the LLVM
# package definitions in the "CMakeLists.txt" files for multiple subdirs.
#
find_package(LLVM REQUIRED CONFIG NO_CMAKE_BUILDS_PATH)
message(STATUS "Found LLVM ${LLVM_PACKAGE_VERSION}")
message(STATUS "Using LLVMConfig.cmake in ${LLVM_DIR}")
if (${LLVM_PACKAGE_VERSION} VERSION_LESS "9.0")
  message(FATAL_ERROR "C-Vise requires LLVM 9.0 or later")
endif()
#
# Do this here, too, just to keep it with the LLVM check above.
#
find_package(Clang REQUIRED CONFIG NO_CMAKE_BUILDS_PATH)
message(STATUS "Using ClangConfig.cmake in ${Clang_DIR}")

# Locate Python and check its version.
#
find_package(PythonInterp 3.6 REQUIRED)

# Locate pytest
execute_process(COMMAND ${PYTHON_EXECUTABLE} -m pytest --version
  OUTPUT_VARIABLE PYTEST_output
  ERROR_VARIABLE  PYTEST_error
  RESULT_VARIABLE PYTEST_result)
if(NOT ${PYTEST_result} EQUAL 0)
  message(WARNING "Pytest package not available: ${PYTEST_error}")
endif()

# Locate Pebble
execute_process(COMMAND ${PYTHON_EXECUTABLE} -c "import pebble"
  OUTPUT_VARIABLE PEBBLE_output
  ERROR_VARIABLE  PEBBLE_error
  RESULT_VARIABLE PEBBLE_result)
if(NOT ${PEBBLE_result} EQUAL 0)
  message(WARNING "Pebble package not available: ${PEBBLE_error}")
endif()

# Locate psutil
execute_process(COMMAND ${PYTHON_EXECUTABLE} -c "import psutil"
  OUTPUT_VARIABLE PSUTIL_output
  ERROR_VARIABLE  PSUTIL_error
  RESULT_VARIABLE PSUTIL_result)
if(NOT ${PSUTIL_result} EQUAL 0)
  message(WARNING "psutil package not available: ${PSUTIL_error}")
endif()

# Locate flex.  Do this here because we need the package definitions in the
# "CMakeLists.txt" files for multiple subdirs.
#
find_package(FLEX REQUIRED)

find_program(UNIFDEF unifdef)
if(NOT UNIFDEF)
  message(WARNING "unifdef not available")
endif()

###############################################################################

# Determine the short git hash for the source tree.
#
## METHOD 1: The source tree is the result of `git archive'.
# `git archive' inserts the abbreviated hash of the archive's commit into this
# file.  (See the `.gitattributes' file.)
#
set(GIT_HASH "$Format:%h$")
if(GIT_HASH MATCHES "^\\$")
  ## METHOD 2: The source tree is a git repository.
  get_git_head_revision(GIT_REFSPEC GIT_HASH)
  if(NOT GIT_HASH STREQUAL "GITDIR-NOTFOUND")
    # Trim to the short hash.
    string(SUBSTRING "${GIT_HASH}" 0 7 GIT_HASH)
  else()
    ## METHOD 3: Give up.
    set(GIT_HASH "unknown")
  endif()
endif()

###############################################################################

# Generate the "config.h" file.
#
set(ENABLE_TRANS_ASSERT ON CACHE BOOL
  "Use assert() in clang_delta transformations.")

check_include_file("dlfcn.h"		HAVE_DLFCN_H)
check_include_file("inttypes.h"		HAVE_INTTYPES_H)
check_include_file("memory.h"		HAVE_MEMORY_H)
check_include_file("stdint.h"		HAVE_STDINT_H)
check_include_file("stdlib.h"		HAVE_STDLIB_H)
check_include_file("strings.h"		HAVE_STRINGS_H)
check_include_file("string.h"		HAVE_STRING_H)
check_include_file("sys/stat.h"		HAVE_SYS_STAT_H)
check_include_file("sys/types.h"	HAVE_SYS_TYPES_H)
check_include_file("unistd.h"		HAVE_UNISTD_H)

set(cvise_PACKAGE             "cvise")
set(cvise_PACKAGE_BUGREPORT   "https://github.com/marxin/cvise/issues")
set(cvise_PACKAGE_NAME        "cvise")
set(cvise_PACKAGE_STRING      "cvise 2.6.0")
set(cvise_PACKAGE_TARNAME     "cvise")
set(cvise_PACKAGE_URL         "https://github.com/marxin/cvise/")
set(cvise_PACKAGE_VERSION     "2.6.0")
set(cvise_VERSION             "2.6.0")
set(cvise_LLVM_VERSION        "${LLVM_PACKAGE_VERSION}")

configure_file("cmake_config.h.in" "${PROJECT_BINARY_DIR}/config.h")
add_definitions("-DHAVE_CONFIG_H")

###############################################################################

# Use option `-fvisibility-inlines-hidden` if the C++ compiler supports it.
# See LLVM file `share/llvm/cmake/HandleLLVMOptions.cmake`.
#
check_cxx_compiler_flag(
  "-fvisibility-inlines-hidden"
  SUPPORTS_FVISIBILITY_INLINES_HIDDEN_FLAG
)

check_cxx_compiler_flag(
  "-Wno-error=mismatched-new-delete"
  SUPPORTS_WMISMATCHED_NEW_DELETE
)

if(CMAKE_CXX_COMPILER_ID STREQUAL "GNU"
    OR CMAKE_CXX_COMPILER_ID STREQUAL "Clang")
  # XXX figure out how to get "-std=c++17 -fno-rtti" from LLVM.  That's how we
  # get those options in the Automake path...
  set(CMAKE_C_FLAGS "${CMAKE_C_FLAGS} -Wall -Wextra -Werror -Wno-error=maybe-uninitialized")
  set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -std=c++17 -fno-rtti -fno-strict-aliasing -Wall -Wextra -Wno-unused-parameter -Werror -Wno-error=maybe-uninitialized")
  if(SUPPORTS_FVISIBILITY_INLINES_HIDDEN_FLAG)
    set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -fvisibility-inlines-hidden")
  endif()
  if(SUPPORTS_WMISMATCHED_NEW_DELETE)
    set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -Wno-error=mismatched-new-delete")
  endif()

  set(CMAKE_CXX_FLAGS_RELEASE "${CMAKE_CXX_FLAGS_RELEASE} -O3")
  set(CMAKE_CXX_FLAGS_RELWITHDEBINFO "${CMAKE_CXX_FLAGS_RELEASE} -O3")
endif()

###############################################################################

# Enable tests
enable_testing()
add_test(NAME all COMMAND ${PYTHON_EXECUTABLE} -m pytest)

###############################################################################

# Needs to be sourced after we have a compiler tested
include(GNUInstallDirs)

add_subdirectory(clang_delta)
add_subdirectory(clex)
add_subdirectory(cvise)
add_subdirectory(delta)

# Copy top-level cvise script
configure_file(
  "${PROJECT_SOURCE_DIR}/cvise.py"
  "${PROJECT_BINARY_DIR}/cvise.py"
  @ONLY
)

configure_file(
  "${PROJECT_SOURCE_DIR}/cvise-delta.py"
  "${PROJECT_BINARY_DIR}/cvise-delta.py"
  @ONLY
)

configure_file(
  "${PROJECT_SOURCE_DIR}/tests/test_cvise.py"
  "${PROJECT_BINARY_DIR}/tests/test_cvise.py"
  COPYONLY
)

configure_file(
  "${PROJECT_SOURCE_DIR}/tests/sources/blocksort-part.c"
  "${PROJECT_BINARY_DIR}/tests/sources/blocksort-part.c"
  COPYONLY
)

configure_file(
  "${PROJECT_SOURCE_DIR}/setup.cfg"
  "${PROJECT_BINARY_DIR}/setup.cfg"
  COPYONLY
)

install(PROGRAMS "${PROJECT_BINARY_DIR}/cvise.py"
  DESTINATION "${CMAKE_INSTALL_BINDIR}"
  RENAME "cvise"
)

install(PROGRAMS "${PROJECT_BINARY_DIR}/cvise-delta.py"
  DESTINATION "${CMAKE_INSTALL_BINDIR}"
  RENAME "cvise-delta"
)

###############################################################################

## End of file.

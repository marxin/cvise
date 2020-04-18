## -*- mode: CMake -*-
##
## Copyright (c) 2012, 2013, 2014, 2015, 2016, 2018, 2019 The University of Utah
## All rights reserved.
##
## This file is distributed under the University of Illinois Open Source
## License.  See the file COPYING for details.

###############################################################################

cmake_minimum_required(VERSION 2.8.12)

project(cvise_python)

###############################################################################

# find_package(LLVM) is done by the topmost "CMakeLists.txt" file.

###############################################################################

# Check for the run-time prerequisites of C-Vise.  We only warn the user when
# these are not found at configure time.  Let the user install the dependencies
# later.
#
find_program(CLANG_FORMAT
  "clang-format${CMAKE_EXECUTABLE_SUFFIX}"
  PATHS "${LLVM_TOOLS_BINARY_DIR}"
  )
if(NOT CLANG_FORMAT)
  message(STATUS "`clang-format${CMAKE_EXECUTABLE_SUFFIX}' was not found")
  set(missing_required_runtime_prereq "yes")
endif()


if(NOT CLANG_FORMAT)
  message(STATUS "`clang-format${CMAKE_EXECUTABLE_SUFFIX}' was not found")
  message("You must install `clang-format' before running C-Vise.")
  set(CLANG_FORMAT "clang-format")
endif()

###############################################################################

# Generate file "cvise.py".
#
configure_file("${cvise_python_SOURCE_DIR}/cvise.py"
  "${cvise_python_BINARY_DIR}/cvise.py"
)

###############################################################################

# Copy the Python modules into the build tree so that we can run C-Vise there.
#
configure_file(
  "${cvise_python_SOURCE_DIR}/__init__.py"
  "${cvise_python_BINARY_DIR}/__init__.py"
  COPYONLY
)
configure_file(
  "${cvise_python_SOURCE_DIR}/pass_groups/all.json"
  "${cvise_python_BINARY_DIR}/pass_groups/all.json"
  COPYONLY
)
configure_file(
  "${cvise_python_SOURCE_DIR}/pass_groups/opencl-120.json"
  "${cvise_python_BINARY_DIR}/pass_groups/opencl-120.json"
  COPYONLY
)
configure_file(
  "${cvise_python_SOURCE_DIR}/passes/__init__.py"
  "${cvise_python_BINARY_DIR}/passes/__init__.py"
  COPYONLY
)
configure_file(
  "${cvise_python_SOURCE_DIR}/passes/abstract.py"
  "${cvise_python_BINARY_DIR}/passes/abstract.py"
  COPYONLY
)
configure_file(
  "${cvise_python_SOURCE_DIR}/passes/balanced.py"
  "${cvise_python_BINARY_DIR}/passes/balanced.py"
  COPYONLY
)
configure_file(
  "${cvise_python_SOURCE_DIR}/passes/blank.py"
  "${cvise_python_BINARY_DIR}/passes/blank.py"
  COPYONLY
)
configure_file(
  "${cvise_python_SOURCE_DIR}/passes/clang.py"
  "${cvise_python_BINARY_DIR}/passes/clang.py"
  COPYONLY
)
configure_file(
  "${cvise_python_SOURCE_DIR}/passes/clangbinarysearch.py"
  "${cvise_python_BINARY_DIR}/passes/clangbinarysearch.py"
  COPYONLY
)
configure_file(
  "${cvise_python_SOURCE_DIR}/passes/clex.py"
  "${cvise_python_BINARY_DIR}/passes/clex.py"
  COPYONLY
)
configure_file(
  "${cvise_python_SOURCE_DIR}/passes/comments.py"
  "${cvise_python_BINARY_DIR}/passes/comments.py"
  COPYONLY
)
configure_file(
  "${cvise_python_SOURCE_DIR}/passes/ifs.py"
  "${cvise_python_BINARY_DIR}/passes/ifs.py"
  COPYONLY
)
configure_file(
  "${cvise_python_SOURCE_DIR}/passes/includeincludes.py"
  "${cvise_python_BINARY_DIR}/passes/includeincludes.py"
  COPYONLY
)
configure_file(
  "${cvise_python_SOURCE_DIR}/passes/includes.py"
  "${cvise_python_BINARY_DIR}/passes/includes.py"
  COPYONLY
)
configure_file(
  "${cvise_python_SOURCE_DIR}/passes/indent.py"
  "${cvise_python_BINARY_DIR}/passes/indent.py"
  COPYONLY
)
configure_file(
  "${cvise_python_SOURCE_DIR}/passes/ints.py"
  "${cvise_python_BINARY_DIR}/passes/ints.py"
  COPYONLY
)
configure_file(
  "${cvise_python_SOURCE_DIR}/passes/line_markers.py"
  "${cvise_python_BINARY_DIR}/passes/line_markers.py"
  COPYONLY
)
configure_file(
  "${cvise_python_SOURCE_DIR}/passes/lines.py"
  "${cvise_python_BINARY_DIR}/passes/lines.py"
  COPYONLY
)
configure_file(
  "${cvise_python_SOURCE_DIR}/passes/peep.py"
  "${cvise_python_BINARY_DIR}/passes/peep.py"
  COPYONLY
)
configure_file(
  "${cvise_python_SOURCE_DIR}/passes/special.py"
  "${cvise_python_BINARY_DIR}/passes/special.py"
  COPYONLY
)
configure_file(
  "${cvise_python_SOURCE_DIR}/passes/ternary.py"
  "${cvise_python_BINARY_DIR}/passes/ternary.py"
  COPYONLY
)
configure_file(
  "${cvise_python_SOURCE_DIR}/passes/unifdef.py"
  "${cvise_python_BINARY_DIR}/passes/unifdef.py"
  COPYONLY
)
configure_file(
  "${cvise_python_SOURCE_DIR}/tests/__init__.py"
  "${cvise_python_BINARY_DIR}/tests/__init__.py"
  COPYONLY
)
configure_file(
  "${cvise_python_SOURCE_DIR}/tests/testabstract.py"
  "${cvise_python_BINARY_DIR}/tests/testabstract.py"
  COPYONLY
)
configure_file(
  "${cvise_python_SOURCE_DIR}/tests/test_balanced.py"
  "${cvise_python_BINARY_DIR}/tests/test_balanced.py"
  COPYONLY
)
configure_file(
  "${cvise_python_SOURCE_DIR}/tests/test_comments.py"
  "${cvise_python_BINARY_DIR}/tests/test_comments.py"
  COPYONLY
)
configure_file(
  "${cvise_python_SOURCE_DIR}/tests/test_ifs.py"
  "${cvise_python_BINARY_DIR}/tests/test_ifs.py"
  COPYONLY
)
configure_file(
  "${cvise_python_SOURCE_DIR}/tests/test_ints.py"
  "${cvise_python_BINARY_DIR}/tests/test_ints.py"
  COPYONLY
)
configure_file(
  "${cvise_python_SOURCE_DIR}/tests/test_line_markers.py"
  "${cvise_python_BINARY_DIR}/tests/test_line_markers.py"
  COPYONLY
)
configure_file(
  "${cvise_python_SOURCE_DIR}/tests/test_nestedmatcher.py"
  "${cvise_python_BINARY_DIR}/tests/test_nestedmatcher.py"
  COPYONLY
)
configure_file(
  "${cvise_python_SOURCE_DIR}/tests/test_peep.py"
  "${cvise_python_BINARY_DIR}/tests/test_peep.py"
  COPYONLY
)
configure_file(
  "${cvise_python_SOURCE_DIR}/tests/test_special.py"
  "${cvise_python_BINARY_DIR}/tests/test_special.py"
  COPYONLY
)
configure_file(
  "${cvise_python_SOURCE_DIR}/tests/test_ternary.py"
  "${cvise_python_BINARY_DIR}/tests/test_ternary.py"
  COPYONLY
)
configure_file(
  "${cvise_python_SOURCE_DIR}/utils/__init__.py"
  "${cvise_python_BINARY_DIR}/utils/__init__.py"
  COPYONLY
)
configure_file(
  "${cvise_python_SOURCE_DIR}/utils/compat.py"
  "${cvise_python_BINARY_DIR}/utils/compat.py"
  COPYONLY
)
configure_file(
  "${cvise_python_SOURCE_DIR}/utils/error.py"
  "${cvise_python_BINARY_DIR}/utils/error.py"
  COPYONLY
)
configure_file(
  "${cvise_python_SOURCE_DIR}/utils/info.py"
  "${cvise_python_BINARY_DIR}/utils/info.py"
  COPYONLY
)
configure_file(
  "${cvise_python_SOURCE_DIR}/utils/nestedmatcher.py"
  "${cvise_python_BINARY_DIR}/utils/nestedmatcher.py"
  COPYONLY
)
configure_file(
  "${cvise_python_SOURCE_DIR}/utils/readkey.py"
  "${cvise_python_BINARY_DIR}/utils/readkey.py"
  COPYONLY
)
configure_file(
  "${cvise_python_SOURCE_DIR}/utils/statistics.py"
  "${cvise_python_BINARY_DIR}/utils/statistics.py"
  COPYONLY
)
configure_file(
  "${cvise_python_SOURCE_DIR}/utils/testing.py"
  "${cvise_python_BINARY_DIR}/utils/testing.py"
  COPYONLY
)

###############################################################################

install(DIRECTORY "${cvise_python_BINARY_DIR}/"
  DESTINATION "${CMAKE_INSTALL_PREFIX}/share/${cvise_PACKAGE}"
  FILES_MATCHING
  PATTERN "*.py"
  PATTERN "*.json"
  PATTERN "__pycache__" EXCLUDE
  PATTERN "CMakeFiles" EXCLUDE
)

###############################################################################

## End of file.

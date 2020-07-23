#!/usr/bin/bash

BUILD_TYPE=$1

rm -rf objdir
mkdir objdir
cd objdir
cmake .. -DCMAKE_BUILD_TYPE=$BUILD_TYPE
make -j`nproc` VERBOSE=1

if [ "$BUILD_TYPE" = "COVERAGE" ]; then
coverage run --source=. -m pytest cvise/tests/
coverage report -m
COVERALLS_REPO_TOKEN=hLV67xXTIENsuN4tmJoK0RpfgNZQW72sK coveralls -n
COVERALLS_REPO_TOKEN=hLV67xXTIENsuN4tmJoK0RpfgNZQW72sK coveralls --gcov-options '\-lp' --exclude-pattern '.*\.l'
else
pytest
fi

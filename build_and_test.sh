#!/usr/bin/bash

BUILD_TYPE=$1

rm -rf objdir && \
mkdir objdir && \
cd objdir && \
cmake .. -DCMAKE_BUILD_TYPE=$BUILD_TYPE && \
make -j`nproc` VERBOSE=1 && \
pytest

if [ "$BUILD_TYPE" = "COVERAGE" ]; then
coverage run --source=cvise -m pytest cvise/tests/
COVERALLS_REPO_TOKEN=hLV67xXTIENsuN4tmJoK0RpfgNZQW72sK coveralls
COVERALLS_REPO_TOKEN=hLV67xXTIENsuN4tmJoK0RpfgNZQW72sK coveralls --gcov-options '\-lp' --exclude-pattern '.*\.l'
fi

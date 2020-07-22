#!/usr/bin/bash

mkdir objdir && \
cd objdir && \
cmake .. -DCMAKE_BUILD_TYPE=$BUILD_TYPE && \
make -j2 VERBOSE=1 && \
pytest

if [ "$1" = "yes" ]; then
coverage run --source=cvise -m pytest cvise/tests/
COVERALLS_REPO_TOKEN=hLV67xXTIENsuN4tmJoK0RpfgNZQW72sK coveralls
fi

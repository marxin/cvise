#!/usr/bin/env bash

BUILD_TYPE=$1

rm -rf objdir
mkdir objdir
cd objdir
cmake .. -DCMAKE_BUILD_TYPE=$BUILD_TYPE
make -j`nproc` VERBOSE=1

if [ "$BUILD_TYPE" = "COVERAGE" ]; then
pytest --cov=./
CODECOV_TOKEN="7c181327-be77-41de-aa6e-ca7187b14376" codecov
else
pytest
fi

#!/usr/bin/bash

mkdir objdir && \
cd objdir && \
cmake .. -DCMAKE_BUILD_TYPE=$BUILD_TYPE && \
make -j2 VERBOSE=1 && \
pytest && \
coverage run --source=cvise -m pytest cvise/tests/ && \
coveralls

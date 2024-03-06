#!/usr/bin/env python3

import subprocess
import sys

if '--help' in sys.argv:
    print(
        'C-Vise implementation of delta tool: ./cvise-delta script '
        'INTERESTINGNESS_TEST TEST_CASE [TEST_CASE ...] [--arguments]'
    )
    exit(0)

subprocess.run(['cvise', '--pass-group=delta'] + sys.argv[1:])

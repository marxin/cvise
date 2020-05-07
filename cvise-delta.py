#!/usr/bin/env python3

import argparse
import subprocess

parser = argparse.ArgumentParser(description='C-Vise implementation of delta tool')
parser.add_argument('args', nargs='+', help='Arguments passed to cvise')

args = parser.parse_args()
subprocess.run(['cvise', '--pass-group=delta'] + args.args)

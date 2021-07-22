#!/bin/bash

set -e

cd /io
yum install -y $PACKAGE_LIST
python3 test-script.py

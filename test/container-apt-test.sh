#!/bin/bash

set -e

cd /io
apt-get update
apt-get install -y $PACKAGE_LIST
python3 test-script.py

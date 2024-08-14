#!/bin/bash

set -e

source .test/bin/activate
cd /io
pip3 install --progress-bar off --upgrade pip

# Check if we will have a mismatch between latest release and wheel, by doing a dry-run
pip3 install --dry-run --progress-bar off --report pip_latest.json $PIP_EXTRA_ARGS $PACKAGE_LIST &> dryrun_output.log

pip3 install --prefer-binary --progress-bar off --report pip_binary.json $PIP_EXTRA_ARGS $PACKAGE_LIST
python3 test-script.py

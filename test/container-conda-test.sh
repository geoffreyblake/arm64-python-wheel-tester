#!/bin/bash

set -e

cd /io
source $HOME/anaconda/etc/profile.d/conda.sh
conda create -n my-env
conda activate my-env
conda install $PACKAGE_LIST

python3 test-script.py

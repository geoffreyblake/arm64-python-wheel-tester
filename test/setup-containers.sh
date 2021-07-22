#!/bin/bash

# change to the directory containing this script
cd "$( dirname "${BASH_SOURCE[0]}" )"

# fetch the latest version of each base image
for image in 'ubuntu:focal' 'amazonlinux' 'centos:8'; do
    docker pull ${image}
done

for image in 'focal' 'amazon-linux2' 'centos8' 'centos8-py38' 'testhost'; do
    docker build -t ${image} -f docker/Dockerfile.${image} .
done

#docker image prune -y

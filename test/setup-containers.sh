#!/bin/bash

set -ex

# change to the directory containing this script
cd "$( dirname "${BASH_SOURCE[0]}" )"

# fetch the latest version of each base image
for image in 'ubuntu:focal' 'amazonlinux' 'centos:8'; do
    docker pull ${image}
done

for image in 'focal' 'amazon-linux2' 'centos8' 'centos8-py38'; do
    docker build -t ${image} -f docker/Dockerfile.${image} .
done

image=testhost
docker build -t ${image} -f docker/Dockerfile.${image} \
           --build-arg USER_GID="$(id -g)" \
           --build-arg USER_UID="$(id -u)" \
           --build-arg USER_NAME="$(whoami)" \
           --build-arg DOCKER_GID="$(stat -c '%g' /var/run/docker.sock)" \
           .
#docker image prune -y

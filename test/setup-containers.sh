#!/bin/bash

set -ex

# change to the directory containing this script
cd "$( dirname "${BASH_SOURCE[0]}" )"

# fetch the latest version of each base image
for image in 'ubuntu:focal' 'amazonlinux'; do
    docker pull ${image}
done

for image in 'focal' 'jammy' 'amazon-linux2' 'amazon-linux2-py38'; do
    docker build -t wheel-tester/${image} -f docker/Dockerfile.${image} .
done

image=testhost
docker build -t wheel-tester/${image} -f docker/Dockerfile.${image} \
           --build-arg USER_GID="$(id -g)" \
           --build-arg USER_UID="$(id -u)" \
           --build-arg USER_NAME="$(whoami)" \
           --build-arg DOCKER_GID="$(stat -c '%g' /var/run/docker.sock)" \
           .
#docker image prune -y

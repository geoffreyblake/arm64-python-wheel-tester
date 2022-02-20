#!/bin/bash

cd "$( dirname "${BASH_SOURCE[0]}" )/.."

docker run -it --rm \
    -u $(id -u) \
    -v /var/run/docker.sock:/var/run/docker.sock \
    -v $(pwd)/test:/io \
    -v $(pwd):/repo \
    --env WORK_PATH=$(realpath test) \
    --env GITHUB_REPOSITORY="geoffreyblake/arm64-python-wheel-tester" \
    --env GITHUB_API_URL="https://api.github.com" \
    --network host \
    wheel-tester/testhost

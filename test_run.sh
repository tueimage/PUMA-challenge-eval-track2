#!/usr/bin/env bash

# Stop at first error
set -e

SCRIPT_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )
DOCKER_TAG="puma-challenge-evaluation-track2"
DOCKER_NOOP_VOLUME="${DOCKER_TAG}-volume"

INPUT_DIR="${SCRIPT_DIR}/input"
OUTPUT_DIR="${SCRIPT_DIR}/output"


echo "=+= (Re)build the container"
docker build "$SCRIPT_DIR" \
  --platform=linux/amd64 \
  --tag $DOCKER_TAG 2>&1

docker volume create puma-eval-output

echo "=+= Doing an evaluation"
docker volume create "$DOCKER_NOOP_VOLUME" > /dev/null
docker run --rm \
    --memory=4g \
    --platform=linux/amd64 \
    --network none \
    --gpus all \
    -v $SCRIPT_DIR/test/:/input/ \
    -v puma-eval-output:/output/ \
    --volume "$DOCKER_NOOP_VOLUME":/tmp \
    $DOCKER_TAG
docker volume rm "$DOCKER_NOOP_VOLUME" > /dev/null


# Ensure permissions are set correctly on the output
# This allows the host user (e.g. you) to access and handle these files
docker run --rm \
    --quiet \
    --env HOST_UID=`id --user` \
    --env HOST_GID=`id --group` \
    --volume "$OUTPUT_DIR":/output \
    alpine:latest \
    /bin/sh -c 'chown -R ${HOST_UID}:${HOST_GID} /output'


# Check if the output files exist after the container has run
echo "=+= Checking output files..."
docker run --rm \
    -v puma-eval-output:/output/ \
    python:3.7-slim sh -c "ls /output/"

EXPECTED_FILE_METRICS="/output/metrics.json"
if docker run --rm -v puma-eval-output:/output/ python:3.7-slim sh -c "[ -f $EXPECTED_FILE_METRICS ]"; then
    echo "=+= Expected output for metrics is correct."

    # Copy metrics.json to the output directory
    docker run --rm -v puma-eval-output:/output/ -v "$OUTPUT_DIR":/local_output python:3.7-slim sh -c "cp $EXPECTED_FILE_METRICS /local_output/"
    echo "=+= metrics.json copied to ${OUTPUT_DIR}."
else
    echo "=+= Expected output for metrics not found!"
    exit 1
fi


echo "=+= Wrote results to ${OUTPUT_DIR}"

echo "=+= Save this image for uploading via save.sh \"${DOCKER_TAG}\""

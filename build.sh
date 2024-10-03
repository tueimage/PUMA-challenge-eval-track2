#!/usr/bin/env bash
SCRIPTPATH="$( cd "$(dirname "$0")" ; pwd -P )"

docker build -t puma-challenge-evaluation-track1 "$SCRIPTPATH"
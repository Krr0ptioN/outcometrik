#!/usr/bin/env sh
set -eu
exec docker compose -f infra/compose.yaml up --build "$@"

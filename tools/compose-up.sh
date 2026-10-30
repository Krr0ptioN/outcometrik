#!/usr/bin/env sh
set -eu
. "$(dirname "$0")/setup-dev-env.sh"
exec docker compose -f infra/compose.yaml up --build "$@"

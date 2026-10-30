#!/usr/bin/env sh
set -eu

# Source this file before running Django or Compose locally. Values are generated
# for the current shell and are never written to the repository.
if [ -z "${DJANGO_SECRET_KEY:-}" ]; then
  DJANGO_SECRET_KEY="$(python3 -c 'import secrets; print(secrets.token_urlsafe(48))')"
  export DJANGO_SECRET_KEY
fi
if [ -z "${POSTGRES_PASSWORD:-}" ]; then
  POSTGRES_PASSWORD="$(python3 -c 'import secrets; print(secrets.token_urlsafe(24))')"
  export POSTGRES_PASSWORD
fi

export DJANGO_DEBUG="${DJANGO_DEBUG:-true}"
export DJANGO_ALLOWED_HOSTS="${DJANGO_ALLOWED_HOSTS:-localhost,127.0.0.1,api}"
export POSTGRES_DB="${POSTGRES_DB:-outcometrik}"
export POSTGRES_USER="${POSTGRES_USER:-outcometrik}"
export POSTGRES_HOST="${POSTGRES_HOST:-localhost}"
export POSTGRES_PORT="${POSTGRES_PORT:-5432}"
export CELERY_BROKER_URL="${CELERY_BROKER_URL:-redis://localhost:6379/0}"
export CELERY_RESULT_BACKEND="${CELERY_RESULT_BACKEND:-redis://localhost:6379/1}"
export COMPOSE_POSTGRES_HOST="${COMPOSE_POSTGRES_HOST:-db}"
export COMPOSE_CELERY_BROKER_URL="${COMPOSE_CELERY_BROKER_URL:-redis://redis:6379/0}"
export COMPOSE_CELERY_RESULT_BACKEND="${COMPOSE_CELERY_RESULT_BACKEND:-redis://redis:6379/1}"

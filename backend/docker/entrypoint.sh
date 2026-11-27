#!/bin/sh
set -e

if [ "${MIGRATE_ON_START:-true}" = "true" ]; then
    python -m alembic upgrade head
fi

exec "$@"

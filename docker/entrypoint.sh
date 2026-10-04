#!/usr/bin/env sh
# Apply migrations and seed reference data before starting the server.
set -eu

if [ "${SKIP_MIGRATIONS:-0}" != "1" ]; then
  echo "[entrypoint] applying database migrations"
  flask db upgrade
  echo "[entrypoint] seeding reference data (roles, categories)"
  flask seed reference
  if [ "${SEED_DEMO_DATA:-0}" = "1" ]; then
    echo "[entrypoint] seeding demo data"
    flask seed demo
  fi
fi

exec "$@"

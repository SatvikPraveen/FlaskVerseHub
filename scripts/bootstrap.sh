#!/usr/bin/env bash
# One-shot developer setup: virtualenv, dependencies, pre-commit, database, demo data.
set -euo pipefail
cd "$(dirname "$0")/.."

PYTHON=${PYTHON:-python3}
echo "==> creating virtual environment with $($PYTHON --version)"
$PYTHON -m venv .venv
.venv/bin/pip install --upgrade pip wheel >/dev/null
echo "==> installing dependencies"
.venv/bin/pip install -r requirements/dev.txt >/dev/null
.venv/bin/pip install -e . --no-deps >/dev/null
.venv/bin/pre-commit install >/dev/null
[ -f .env ] || cp .env.example .env
echo "==> initialising the development database"
FLASK_APP=wsgi:app FLASK_CONFIG=development .venv/bin/flask db upgrade
FLASK_APP=wsgi:app FLASK_CONFIG=development .venv/bin/flask seed all
cat <<MSG

Done. Next steps:
  source .venv/bin/activate
  make run            # http://127.0.0.1:5000  (admin / AdminPass123!)
  make test           # run the test-suite with the coverage gate
  make experiment     # reproduce the retrieval benchmark
MSG

#!/usr/bin/env bash
# The exact checks CI runs, in order. Exit code is non-zero on the first failure.
set -euo pipefail
cd "$(dirname "$0")/.."
BIN=${BIN:-.venv/bin}
echo "==> ruff";     $BIN/ruff check . && $BIN/ruff format --check .
echo "==> mypy";     $BIN/mypy
echo "==> bandit";   $BIN/bandit -c pyproject.toml -r app -q
echo "==> pytest";   $BIN/pytest --cov --cov-report=term -m "not slow"
echo "All checks passed."

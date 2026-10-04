# 0008 – Single pyproject-based toolchain (ruff, mypy, pytest)

**Status:** Accepted · **Date:** 2026-10-03

## Context

Configuration was spread across `setup.cfg`, `pytest.ini` (with an invalid
section header, so it was silently ignored) and four overlapping tools
(black, isort, flake8, pylint).

## Decision

Configure packaging, ruff (lint + format, including security, bugbear,
pyupgrade and timezone rules), mypy, pytest and coverage in `pyproject.toml`;
expose the canonical commands through `Makefile`, `scripts/check.sh` and
pre-commit; run the same commands in CI.

## Consequences

* One source of truth for every quality gate; local and CI results match.
* Branch coverage is enforced at 85 %; mypy covers application, experiments
  and tests.
* Contributors need only `make install` to get the full toolchain.

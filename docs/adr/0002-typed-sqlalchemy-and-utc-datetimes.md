# 0002 – Typed SQLAlchemy 2.0 models and UTC-normalised timestamps

**Status:** Accepted · **Date:** 2026-10-03

## Context

The original model used untyped `db.Column` declarations, a reserved
`metadata` attribute that prevented import, ambiguous foreign keys, and
timezone-aware Python defaults stored in SQLite, which returns naive values
and made every expiry comparison raise `TypeError`.

## Decision

* Declare models with SQLAlchemy 2.0 `Mapped[]` / `mapped_column` on a typed
  `DeclarativeBase` shared with Flask-SQLAlchemy, and check them with mypy.
* Store every timestamp through `UTCDateTime`, a `TypeDecorator` that writes
  naive UTC and reads back aware UTC on every backend.
* Ban `datetime.utcnow()` via ruff's `DTZ` rules; use `app.utils.time`.

## Consequences

* IDE completion and mypy catch field typos that previously surfaced at
  runtime across the codebase.
* Behaviour is identical on SQLite (tests, development) and PostgreSQL
  (production); comparisons never mix naive and aware values.
* Alembic autogeneration needs a `render_item` hook to render `UTCDateTime`
  as `sa.DateTime()` (configured in the factory).

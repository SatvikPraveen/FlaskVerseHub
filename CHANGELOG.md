# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project
adheres to [Semantic Versioning](https://semver.org/).

## [Unreleased]

## [2.0.0] – 2026-10-03

A ground-up rebuild. The 1.x scaffold could not start (import errors, an
inconsistent model, invalid configuration) and is superseded entirely.

### Added
- Typed SQLAlchemy 2.0 domain model with UTC-normalised timestamps, tags,
  append-only revision history, comments, bookmarks, notifications, hashed
  API keys and an audit trail.
- Service layer shared by HTML, REST and GraphQL interfaces; a single
  visibility policy on the model.
- Authentication: lockout, single-use signed reset tokens, email
  verification, API keys with scopes, role/permission decorators.
- Knowledge Vault: filtered listings, HTML sanitisation, revision diffs and
  restore, bookmarks, threaded comments, bulk actions, JSON/Markdown export.
- Retrieval engine: Porter stemmer, inverted index, BM25 / BM25+ / TF-IDF
  rankers, score explanations, suggestions, cached Flask service.
- Evaluation suite (P@k, R@k, F1, MRR, MAP, nDCG, bootstrap CIs, paired
  significance test) and a seeded synthetic benchmark with committed results
  reproduced by CI.
- REST v1 with OpenAPI 3.1 and Swagger UI; GraphQL with GraphiQL; JWT and
  API-key authentication; uniform problem-document errors.
- Dashboard analytics (including reading-time statistics and a Gini
  coefficient of views), notifications centre, Socket.IO rooms, presence and
  live feed.
- Observability: structlog with request ids, Server-Timing, slow-query
  logging, Prometheus metrics, health probe; hardened security headers.
- Alembic migrations, multi-stage Docker image, Compose stack, CI matrix
  (3.11–3.13, PostgreSQL job, benchmark gate, image smoke test), CodeQL,
  Dependabot, release workflow.
- Documentation: architecture, research notes, API and deployment guides,
  eight ADRs, contributing/security/conduct policies, citation metadata.

### Changed
- Toolchain consolidated into `pyproject.toml` (ruff, mypy, pytest,
  coverage ≥ 85 %).
- Templates rewritten on a single root with Bootstrap 5.

### Removed
- Generated scaffold code, the scaffold generator script, obsolete
  workflows and scripts.

## [1.0.0] – 2025

Initial generated scaffold.

[Unreleased]: https://github.com/SatvikPraveen/FlaskVerseHub/compare/v2.0.0...HEAD
[2.0.0]: https://github.com/SatvikPraveen/FlaskVerseHub/releases/tag/v2.0.0
[1.0.0]: https://github.com/SatvikPraveen/FlaskVerseHub/commits/5378194

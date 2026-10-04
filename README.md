<div align="center">

<img src="app/static/images/logo.svg" alt="" width="72" height="72" />

# FlaskVerseHub

**A research-grade Flask reference platform: typed domain model, REST and GraphQL APIs, real-time events, observability, and a reproducible information-retrieval benchmark.**

[![CI](https://img.shields.io/github/actions/workflow/status/SatvikPraveen/FlaskVerseHub/ci.yml?branch=main&label=CI&logo=github)](https://github.com/SatvikPraveen/FlaskVerseHub/actions/workflows/ci.yml)
[![CodeQL](https://img.shields.io/github/actions/workflow/status/SatvikPraveen/FlaskVerseHub/codeql.yml?branch=main&label=CodeQL&logo=github)](https://github.com/SatvikPraveen/FlaskVerseHub/actions/workflows/codeql.yml)
[![Coverage](https://img.shields.io/codecov/c/github/SatvikPraveen/FlaskVerseHub?logo=codecov)](https://codecov.io/gh/SatvikPraveen/FlaskVerseHub)
[![Python](https://img.shields.io/badge/python-3.11%20%7C%203.12%20%7C%203.13-3776AB?logo=python&logoColor=white)](pyproject.toml)
[![Flask](https://img.shields.io/badge/Flask-3.x-000000?logo=flask)](https://flask.palletsprojects.com/)
[![Ruff](https://img.shields.io/badge/linting-ruff-261230?logo=ruff&logoColor=white)](https://docs.astral.sh/ruff/)
[![Checked with mypy](https://img.shields.io/badge/types-mypy-blue)](https://mypy-lang.org/)
[![License: MIT](https://img.shields.io/badge/license-MIT-yellow)](LICENSE)

[Quick start](#quick-start) · [Architecture](#architecture) · [Retrieval research](#retrieval-research) · [API](#api) · [Documentation](#documentation)

</div>

---

## Overview

FlaskVerseHub is a knowledge-management application built to be *read, measured and extended*. It exercises the full breadth of Flask development in one coherent codebase and treats the hard parts, search ranking, authorization, and observability, with the rigour of a research artefact:

- **One domain, three interfaces.** Server-rendered pages, a versioned REST API with an OpenAPI 3.1 document, and a GraphQL schema all call the same service layer. Visibility and permission rules are written once, on the model, and enforced everywhere.
- **A retrieval engine from first principles.** BM25, BM25+ and TF-IDF are implemented and documented with their references, evaluated with nDCG, MAP and MRR, and benchmarked on a seeded synthetic collection with bootstrap confidence intervals and paired significance tests. CI re-runs the experiment and fails if the committed results do not reproduce bit-for-bit.
- **Production-shaped engineering.** Typed SQLAlchemy 2.0 models checked by mypy, timezone-correct timestamps on every backend, append-only revision history, structured logs with request correlation, Prometheus metrics, hardened headers, hashed API keys, JWT refresh flows, Alembic migrations, a multi-stage container and a 96 % branch-covered test-suite.

## Feature summary

| Area | What is included |
|---|---|
| Knowledge Vault | CRUD with HTML sanitisation, tags, categories, difficulty levels, draft/published/archived workflow, revision history with word-level diffs and restore, bookmarks, threaded comments, bulk actions, JSON/Markdown export |
| Search | Porter-stemmed inverted index, BM25 / BM25+ / TF-IDF rankers, field boosting, per-term score explanations, query suggestions, visibility-aware results, per-user cached index |
| Accounts | Registration with email verification, lockout after repeated failures, single-use password-reset tokens, profile and preferences, API keys with scopes, role and permission decorators |
| APIs | REST v1 (`/api/v1`) with Swagger UI, GraphQL with GraphiQL, Bearer JWT and `X-API-Key` authentication, uniform problem-document errors with request ids, rate limiting |
| Real-time | Socket.IO rooms per user and per item, presence, live item feed, in-app notifications pushed instantly |
| Dashboard | Personal overview, admin analytics (Chart.js) including reading-time statistics and a Gini coefficient of view concentration, notifications centre, audit trail |
| Operations | structlog logging, `X-Request-ID` propagation, Server-Timing, slow-query detection, `/health` and `/metrics`, CSP and security headers, Docker + Compose, GitHub Actions matrix, CodeQL, Dependabot |

## Quick start

### Local (Python 3.11+)

```bash
git clone https://github.com/SatvikPraveen/FlaskVerseHub.git
cd FlaskVerseHub
./scripts/bootstrap.sh          # venv, dependencies, pre-commit, migrations, demo data
source .venv/bin/activate
make run                        # http://127.0.0.1:5000
```

Demo accounts: `admin / AdminPass123!`, `alice / AlicePass123!`, `bob / BobPass123!`.

### Docker Compose (PostgreSQL + Redis)

```bash
docker compose -f docker/docker-compose.yml up --build
```

The stack applies migrations, seeds reference and demo data, and serves on <http://localhost:8000>.

### Everyday commands

```bash
make test          # pytest with the 85 % coverage gate
make lint          # ruff lint + format check
make typecheck     # mypy over app, experiments and tests
make security      # bandit
make experiment    # reproduce the retrieval benchmark into experiments/results/
make help          # everything else
```

## Architecture

```
            ┌──────────────┐   ┌──────────────┐   ┌──────────────┐   ┌──────────────┐
  Clients   │  HTML pages  │   │  REST  v1    │   │   GraphQL    │   │  Socket.IO   │
            └──────┬───────┘   └──────┬───────┘   └──────┬───────┘   └──────┬───────┘
                   │                  │                  │                  │
            ┌──────▼──────────────────▼──────────────────▼──────────────────▼───────┐
  Services  │  auth.service · knowledge_vault.service · search.service · analytics  │
            │  services.activity (audit) · services.notifications · services.events │
            └──────────────────────────────┬────────────────────────────────────────┘
                                           │
            ┌──────────────────────────────▼────────────────────────────────────────┐
  Domain    │  SQLAlchemy 2.0 models (visibility policy, revisions, roles, API keys)│
            │  app.search: Analyzer → InvertedIndex → Ranker (BM25 / BM25+ / TF-IDF)│
            └──────────────────────────────┬────────────────────────────────────────┘
                                           │
            ┌──────────────────────────────▼────────────────────────────────────────┐
  Platform  │  PostgreSQL / SQLite · Redis (cache, limits, socket queue) · Alembic  │
            │  structlog · Prometheus · gunicorn + gevent-websocket · Docker        │
            └───────────────────────────────────────────────────────────────────────┘
```

Key decisions are recorded as [architecture decision records](docs/adr/) and the full design is described in [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

### Repository layout

```
app/
  __init__.py          application factory, blueprint table, template helpers
  config.py            environment-driven profiles (development / testing / production)
  models.py            typed domain model and ORM event hooks
  auth/                forms, routes, service layer, timed tokens, authorization decorators
  knowledge_vault/     item CRUD, revisions, comments, bookmarks, bulk actions
  api_hub/             REST v1, OpenAPI 3.1 generator, GraphQL schema, API auth
  dashboard/           analytics queries, notifications, Socket.IO handlers
  search/              analyzer, inverted index, rankers, metrics, Flask service
  services/            audit trail, notifications, real-time domain events
  security/            nh3 sanitisation, response hardening
  observability.py     logging, request ids, timing, Prometheus
  errors/              negotiated JSON / HTML error handling
  templates/, static/  Bootstrap 5 UI
experiments/           synthetic corpus generator, benchmark runner, committed results
migrations/            Alembic environment and versions
tests/                 unit, integration, api and research suites (311 tests)
docker/                multi-stage Dockerfile, gunicorn config, Compose stack
docs/                  architecture, research notes, API and deployment guides, ADRs
```

## Retrieval research

The search engine is treated as an experimental system. `experiments/` contains a seeded synthetic collection with exact graded relevance (topics and subtopics, inflected word forms, log-normal document lengths, keyword-stuffed hard negatives) and a configuration-driven benchmark that reports every metric with 95 % bootstrap confidence intervals and a paired bootstrap test against a baseline.

Headline results from [`experiments/results/REPORT.md`](experiments/results/REPORT.md) (nDCG@10, 600 documents, 96 queries, seed 42):

| System | nDCG@10 | vs. baseline |
|---|---|---|
| BM25+ (δ = 1) with Porter stemming | 0.962 | n.s. |
| **BM25 (k₁ = 1.5, b = 0.75) with Porter stemming** (baseline) | **0.961** | — |
| BM25 without length normalisation (b = 0) | 0.955 | p < 0.05 |
| TF-IDF cosine (lnc.ltc) with Porter stemming | 0.954 | p < 0.01 |
| BM25 (k₁ = 1.5, b = 0.75) without stemming | 0.941 | p < 0.001 |

The findings match the literature: stemming and document-length normalisation matter, k₁ in the usual range has at most a marginal effect (k₁ = 2.0 sits at the p = 0.05 boundary), and BM25 outperforms the vector-space baseline. Methodology, caveats and how to extend the experiment are in [docs/RESEARCH.md](docs/RESEARCH.md). Reproduce with `make experiment`; CI asserts the committed numbers.

## API

Interactive documentation is served at `/api/v1/docs` (Swagger UI) and `/api/v1/graphql` (GraphiQL).

```bash
# Obtain a token
curl -s -X POST http://localhost:5000/api/v1/auth/token \
  -H 'Content-Type: application/json' \
  -d '{"identifier": "alice", "password": "AlicePass123!"}' | jq -r .access_token

# Ranked search with per-hit scores and analysed terms
curl -s 'http://localhost:5000/api/v1/search?q=flask+blueprints' | jq '.ranker, .terms, .data[0].score'

# Explain why an item scored what it did
curl -s 'http://localhost:5000/api/v1/items/<slug>/explain?q=blueprints' | jq .data.terms

# GraphQL
curl -s -X POST http://localhost:5000/api/v1/graphql -H 'Content-Type: application/json' \
  -d '{"query": "{ search(query: \"sqlalchemy\", perPage: 3) { ranker items { title score } } }"}'
```

Every error is a problem document, `{"error", "message", "status", "details?", "request_id"}`, and every response carries `X-Request-ID` for correlation with the structured logs. See [docs/API.md](docs/API.md).

## Quality

| Check | Tooling | Gate |
|---|---|---|
| Tests | pytest, Hypothesis, pytest-benchmark | 311 tests, branch coverage ≥ 85 % (currently 96 %) |
| Static analysis | ruff (lint + format), mypy, bandit | zero findings |
| Security | CodeQL, Dependabot, CSP and hardened headers, nh3 sanitisation, hashed API keys | weekly scans |
| Reproducibility | seeded experiments, committed results, CI equality check | exact match |

## Configuration

All settings are environment variables with safe defaults; see [`.env.example`](.env.example) for the full list. The most important:

| Variable | Purpose | Default |
|---|---|---|
| `FLASK_CONFIG` | `development`, `testing` or `production` | `development` |
| `SECRET_KEY` | Session, CSRF and JWT signing (required in production) | placeholder |
| `DATABASE_URL` | SQLAlchemy URL (required in production) | SQLite under `instance/` |
| `CACHE_TYPE`, `CACHE_REDIS_URL` | Flask-Caching backend | `SimpleCache` |
| `RATELIMIT_STORAGE_URI` | Flask-Limiter storage | `memory://` |
| `SOCKETIO_MESSAGE_QUEUE` | Redis URL for multi-worker Socket.IO | unset |
| `SEARCH_RANKER`, `SEARCH_BM25_K1`, `SEARCH_BM25_B` | Retrieval engine | `bm25`, `1.5`, `0.75` |
| `LOG_JSON`, `METRICS_ENABLED`, `SENTRY_DSN` | Observability | `false`, `true`, unset |

## Documentation

- [Architecture](docs/ARCHITECTURE.md) and [decision records](docs/adr/)
- [Retrieval research notes](docs/RESEARCH.md) and the [benchmark report](experiments/results/REPORT.md)
- [API guide](docs/API.md)
- [Deployment guide](docs/DEPLOYMENT.md)
- [Contributing](CONTRIBUTING.md), [Security policy](SECURITY.md), [Code of conduct](CODE_OF_CONDUCT.md)
- [Changelog](CHANGELOG.md)

## Citation

If you use FlaskVerseHub in teaching or research, please cite it (see [`CITATION.cff`](CITATION.cff)):

```bibtex
@software{praveen2026flaskversehub,
  author  = {Praveen, Satvik},
  title   = {FlaskVerseHub: a research-grade Flask reference platform with a reproducible retrieval benchmark},
  year    = {2026},
  version = {2.0.0},
  url     = {https://github.com/SatvikPraveen/FlaskVerseHub}
}
```

## License

Released under the [MIT License](LICENSE). Copyright © 2025–2026 Satvik Praveen.

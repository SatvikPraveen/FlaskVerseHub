# Architecture

This document explains how FlaskVerseHub is put together and why. It is
written for someone who wants to change the system safely. Decisions with
lasting consequences are recorded individually under [`adr/`](adr/).

## 1. Shape of the system

FlaskVerseHub is a modular monolith: one deployable Flask application whose
code is organised by *bounded context* (blueprints) with a shared service
layer and a single domain model. The layering is strict and one-directional:

```
interfaces   →   services   →   domain model   →   platform
(HTML, REST, GraphQL, sockets)   (use-cases)       (SQLAlchemy, search)   (DB, Redis, logging)
```

* **Interfaces** translate HTTP, GraphQL or socket input into service calls
  and map the results to a representation. They contain no business rules.
* **Services** (`app/*/service.py`, `app/services/`) implement use-cases:
  registration, authentication, item editing with revisions, bulk actions,
  bookmarks, comments, notifications, search. They are plain functions that
  can be unit-tested with a database and no HTTP client.
* **Domain model** (`app/models.py`, `app/search/`) owns invariants: slug
  uniqueness, lockout policy, the visibility policy, revision snapshots,
  the ranking functions.
* **Platform** concerns (config, extensions, observability, security
  headers, errors) are initialised by the application factory.

## 2. Application factory

`app.create_app(config_name, overrides)` builds the application in a fixed
order: configuration, extensions, blueprints, cross-cutting infrastructure
(observability, search index invalidation, error handlers, security headers,
CLI), template helpers and shell context. Blueprints are registered from a
single table in `_register_blueprints`, so the URL map is discoverable in one
place:

| Blueprint | Prefix | Responsibility |
|---|---|---|
| `main` | `/` | landing page, site search, about, status, tags, `/health` |
| `auth` | `/auth` | accounts, sessions, password flows, API keys |
| `knowledge_vault` | `/knowledge` | authoring and browsing items |
| `api_hub` | `/api/v1` | REST, OpenAPI, GraphQL |
| `dashboard` | `/dashboard` | personal and admin dashboards, notifications, audit |

Configuration profiles (`app/config.py`) are plain classes read from the
environment. Production refuses to start without `SECRET_KEY` and
`DATABASE_URL`; testing uses an in-memory SQLite database on a `StaticPool`
so the whole test session shares one connection.

## 3. Domain model

The model uses SQLAlchemy 2.0 `Mapped[]` declarations and is type-checked by
mypy. Highlights:

* **`UTCDateTime`** stores naive UTC and returns aware datetimes on every
  backend. SQLite would otherwise return naive values and comparisons would
  raise. All code uses `app.utils.time.utcnow()`; `datetime.utcnow()` is
  banned by ruff's `DTZ` rules.
* **`KnowledgeItem`** is the aggregate root: one author, one optional
  category, many tags, append-only `KnowledgeItemRevision` rows, comments,
  bookmarks and attachments. `bump_version()` snapshots the current state
  before an edit so history is complete and restorable.
* **Visibility policy.** `KnowledgeItem.visible_to(user)` returns the base
  `Select` every reader must start from; `is_visible_to(user)` is the
  per-instance twin. Anonymous users see published public items, users also
  see their own, administrators see everything. Search applies the policy
  *after* scoring so index statistics are not biased by the viewer.
* **Identity.** `User` carries lockout state (`register_failed_login`),
  roles (many-to-many, with a default role attached on insert) and a JSON
  preferences bag. `ApiKey` stores only a SHA-256 hash and a display prefix.
* **Audit.** `Activity` rows are appended by `app.services.activity` from
  every service that mutates state; request metadata is captured when a
  request is active.

Slugs are generated in `before_insert` listeners with a uniqueness probe,
and `published_at` is set when an item first becomes published.

## 4. Services and events

Services return domain objects or raise typed errors
(`DuplicateAccountError`, `PermissionDeniedError`); interfaces decide the
HTTP status. Side effects fan out from the service layer:

* `services.activity.record_activity` – audit trail
* `services.notifications.notify` – in-app notification plus Socket.IO push
  to the user's room
* `services.events` – `item:created|updated|deleted`, `comment:added` to the
  `public` room and `item:<slug>` rooms

Because REST, GraphQL and HTML all call the same functions, every interface
produces identical audit rows, notifications and real-time events.

## 5. Search engine

`app/search` is an independent package (it imports nothing from Flask except
in `service.py`):

```
Analyzer (tokenise → stop words → Porter stem)
   └─▶ InvertedIndex (postings as NumPy arrays, boosted tf, doc lengths)
          └─▶ Ranker.score(index, terms) → ndarray of scores
                 ├─ BM25Ranker        Robertson et al. 1994
                 ├─ BM25PlusRanker    Lv & Zhai 2011
                 └─ TFIDFRanker       Salton & Buckley 1988 (lnc.ltc cosine)
SearchEngine: pagination, post-scoring filters, explain(), suggest()
```

Field boosts are folded into term frequency *and* document length so BM25's
normalisation stays coherent. `service.py` keeps one engine per process,
rebuilt when a `(count, max(updated_at))` fingerprint changes or a TTL
expires, and invalidated eagerly by a session `before_flush` hook.
`app/search/metrics.py` implements the evaluation suite used by
`experiments/`.

## 6. Interfaces

* **HTML** uses Flask-WTF forms, Jinja templates under `app/templates/`
  (one root, blueprint sub-folders) and Bootstrap 5. CSRF is enforced on
  every form; destructive actions are POST-only.
* **REST v1** (`app/api_hub/rest_routes.py`) is CSRF-exempt and
  authenticates with a Bearer JWT (Flask-JWT-Extended, access + refresh) or
  `X-API-Key`. marshmallow schemas define the contract and feed the
  OpenAPI 3.1 generator (`openapi.py`), so documentation cannot drift from
  validation.
* **GraphQL** (`graphql_routes.py`) is a graphene 3 projection of the same
  services with mutations guarded by the same permission checks.
* **Socket.IO** (`dashboard/sockets.py`) authenticates from the session
  cookie and manages rooms; the client in `static/js/socket.js` renders the
  live feed and notification badge.

## 7. Cross-cutting concerns

| Concern | Implementation |
|---|---|
| Errors | `app/errors/handlers.py` negotiates JSON problem documents for `/api/*` or JSON-accepting clients and rendered pages otherwise; every payload carries the request id |
| Logging | structlog with contextvars; `X-Request-ID` generated or propagated and bound to every log line |
| Metrics | `prometheus-flask-exporter` at `/metrics`, build info gauge |
| Timing | `Server-Timing` header; slow queries (≥ 0.5 s) logged with statement and location |
| Security | CSP, `nosniff`, frame denial, referrer and permissions policies, HSTS when cookies are secure; nh3 HTML sanitisation; `session_protection="strong"`; account lockout; rate limits on auth and API |
| Persistence | Alembic migrations in `migrations/`; custom types render as plain SQLAlchemy types; SQLite uses batch mode |

## 8. Testing strategy

* `tests/unit` – models, utilities, config, services (no HTTP)
* `tests/integration` – blueprints through the Flask test client, sockets
  through the Socket.IO test client
* `tests/api` – REST and GraphQL contracts
* `tests/research` – analyzer, index, rankers (with Hypothesis property
  tests), metrics, engine, Flask search service, end-to-end benchmark
  reproducibility

The session-scoped app shares one in-memory database; tables are emptied
after each test. Because the app context stays pushed, request-scoped `g`
state is reset by a test-only `before_request` hook, which mirrors
production behaviour where `g` is fresh per request.

## 9. Deployment

See [DEPLOYMENT.md](DEPLOYMENT.md). In short: gunicorn with
`gevent-websocket` workers behind a TLS-terminating proxy, PostgreSQL, Redis
for cache, rate limits and the Socket.IO message queue, migrations applied by
the container entrypoint, `/health` for readiness and `/metrics` for
Prometheus.

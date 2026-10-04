# Deployment guide

## Topology

```
Internet ─▶ TLS proxy (Caddy / nginx / cloud LB) ─▶ gunicorn (gevent-websocket) ─▶ Flask
                                                      │
                                   PostgreSQL ◀───────┤───────▶ Redis (cache · rate limits · Socket.IO queue)
```

The container image is self-contained: the entrypoint applies Alembic
migrations and seeds reference data (roles, categories) before starting
gunicorn. Horizontal scaling only requires `SOCKETIO_MESSAGE_QUEUE` to point at
Redis so real-time events reach every worker.

## Required configuration

| Variable | Notes |
|---|---|
| `FLASK_CONFIG=production` | enables strict cookies, HSTS, JSON logs |
| `SECRET_KEY` | ≥ 32 random bytes; also signs JWTs unless `JWT_SECRET_KEY` is set |
| `DATABASE_URL` | e.g. `postgresql+psycopg://user:pass@host:5432/db` |
| `CACHE_TYPE=RedisCache`, `CACHE_REDIS_URL` | recommended |
| `RATELIMIT_STORAGE_URI` | Redis URL; `memory://` is per-process only |
| `SOCKETIO_MESSAGE_QUEUE` | Redis URL, mandatory with more than one worker |
| `SESSION_COOKIE_SECURE=true` | default in production; set `false` only for plain-HTTP demos |
| `CORS_ORIGINS` | comma-separated list for the API |
| `SENTRY_DSN` | optional error reporting (`pip install sentry-sdk[flask]` is in `requirements/prod.txt`) |

Production refuses to start when `SECRET_KEY` is the placeholder or
`DATABASE_URL` is missing.

## Docker Compose

```bash
export SECRET_KEY="$(python -c 'import secrets; print(secrets.token_urlsafe(48))')"
export POSTGRES_PASSWORD="$(python -c 'import secrets; print(secrets.token_urlsafe(24))')"
docker compose -f docker/docker-compose.yml up -d --build
docker compose -f docker/docker-compose.yml logs -f web
```

Set `SEED_DEMO_DATA=0` to skip demo users and items. Put a TLS-terminating
proxy in front of port 8000 and forward `X-Forwarded-*` headers
(`FORWARDED_ALLOW_IPS` controls which proxies gunicorn trusts).

## Kubernetes sketch

* Deployment with the GHCR image, `readinessProbe` and `livenessProbe` on
  `GET /health` (returns 503 when the database is unreachable).
* `Service` + `Ingress` with WebSocket support (sticky sessions are not
  required when `SOCKETIO_MESSAGE_QUEUE` is set).
* A pre-upgrade `Job` running `flask db upgrade` is optional; the entrypoint
  is idempotent, but running migrations once avoids concurrent attempts
  during rollouts. Set `SKIP_MIGRATIONS=1` on the web pods in that case.
* Scrape `GET /metrics` with Prometheus; the `flaskversehub_build` gauge
  exposes the version and commit.

## Operations

| Task | Command |
|---|---|
| Create an administrator | `flask users create NAME EMAIL --admin` |
| Unlock an account | `flask users unlock NAME` |
| Apply migrations | `flask db upgrade` |
| Generate a migration | `flask db migrate -m "describe change"` then review the file |
| Rebuild the search index | happens automatically on item writes or after `SEARCH_INDEX_TTL_SECONDS` |
| Run the retrieval benchmark | `python -m experiments.run_retrieval_benchmark` |

## Observability

* Logs are JSON in production (`LOG_JSON=true`) with `request_id`, `method`,
  `path`, `status`, `duration_ms` and `endpoint` on every request line; slow
  queries (`SLOW_QUERY_THRESHOLD_SECONDS`, default 0.5 s) are logged with
  their statement.
* `X-Request-ID` is propagated from the client or generated, returned on the
  response and included in error payloads and pages.
* `Server-Timing: app;dur=…` exposes server latency to browsers.

## Security checklist

- [ ] `SECRET_KEY` and `JWT_SECRET_KEY` set from a secret store
- [ ] TLS terminated in front; `SESSION_COOKIE_SECURE=true`
- [ ] `CORS_ORIGINS` restricted to known origins
- [ ] Redis and PostgreSQL not exposed publicly
- [ ] Rate limits backed by Redis (`RATELIMIT_STORAGE_URI`)
- [ ] Dependabot and CodeQL enabled on the repository (configured in `.github/`)

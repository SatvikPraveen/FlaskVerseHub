# 0007 – Negotiated error representation with request ids

**Status:** Accepted · **Date:** 2026-10-03

## Context

Errors were rendered inconsistently: HTML pages for API consumers, missing
handlers for some status codes, and a `/health` endpoint that always failed.

## Decision

A single set of handlers (`app/errors/handlers.py`) catches `APIError`,
`HTTPException` and unexpected exceptions and renders either a JSON problem
document (`/api/*` paths, JSON bodies, or JSON-preferring `Accept` headers)
or an HTML page. Both carry the request id, which is also bound to every log
line and echoed as `X-Request-ID`.

## Consequences

* Clients can rely on one error shape; support can correlate a report with
  logs using the id shown on the page or in the payload.
* Services raise `APIError` with a status and machine-readable code without
  knowing which interface is active.

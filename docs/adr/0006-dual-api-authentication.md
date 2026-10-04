# 0006 – JWT bearer tokens and hashed API keys for the API

**Status:** Accepted · **Date:** 2026-10-03

## Context

The scaffold protected JSON endpoints with Flask-Login's session decorator,
so unauthenticated API calls were redirected to an HTML login page, and a
custom JWT helper compared naive timestamps so tokens appeared expired.

## Decision

* Browser pages use session cookies with CSRF protection.
* `/api/v1` is CSRF-exempt and accepts either a Flask-JWT-Extended bearer
  token (access + refresh, identity = user id) or an `X-API-Key` whose SHA-256
  hash is stored with a display prefix and scopes (`read`, `write`, `admin`).
* One resolver (`app.api_hub.auth.resolve_api_user`) produces the caller for
  REST and GraphQL alike.

## Consequences

* Machine clients never see HTML; failures are `401`/`403` problem documents.
* Keys can be revoked and audited; the clear text is shown once.
* Scope checks apply to keys only; JWT callers act with full account
  permissions, which keeps the browser-equivalent flow simple.

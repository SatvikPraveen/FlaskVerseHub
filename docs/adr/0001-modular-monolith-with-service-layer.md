# 0001 – Modular monolith with a shared service layer

**Status:** Accepted · **Date:** 2026-10-03

## Context

The generated scaffold placed business rules inside view functions, so the
HTML pages, REST routes and GraphQL resolvers each re-implemented (and
disagreed about) permissions, visibility and side effects. A microservice
split was considered to isolate search and real-time features.

## Decision

Keep one deployable Flask application organised by bounded context
(blueprints), and introduce a service layer (`app/*/service.py`,
`app/services/`) that every interface calls. Interfaces may only translate
input and output; services own use-cases and side effects (audit, notifications,
real-time events); the domain model owns invariants.

## Consequences

* One implementation of each rule; interface tests verify representation,
  service tests verify behaviour.
* The system stays simple to run (`flask run`, one container) while keeping
  module boundaries that would allow extraction later.
* Services must remain framework-light so they can be unit-tested without a
  client; the only Flask dependency allowed is `current_app` configuration.

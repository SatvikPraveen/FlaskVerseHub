# 0004 – First-principles retrieval engine over a search service

**Status:** Accepted · **Date:** 2026-10-03

## Context

Search was a SQL `LIKE` over title and content: no ranking, no
normalisation, no way to explain results. Options considered: PostgreSQL
full-text search, an external engine (Elasticsearch/OpenSearch, Meilisearch),
or an in-process implementation.

## Decision

Implement the ranking stack in `app/search` (analyzer, inverted index,
BM25 / BM25+ / TF-IDF rankers, metrics) in NumPy with no external service, and
expose it through `app.search.service` with a fingerprint/TTL-cached index.

## Consequences

* Every ranking decision is inspectable (`explain`) and testable with
  property-based tests; the engine doubles as teaching material.
* Operationally trivial: no additional service, identical behaviour on SQLite
  and PostgreSQL.
* The in-memory index is rebuilt per process and suits collections up to the
  order of 10⁵ documents; beyond that, the `Ranker` abstraction allows a
  backend swap without touching interfaces.

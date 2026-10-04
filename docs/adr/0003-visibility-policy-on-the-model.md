# 0003 – Visibility policy expressed once on the model

**Status:** Accepted · **Date:** 2026-10-03

## Context

The scaffold's vault listing showed every private item to any authenticated
user, while the REST and GraphQL layers each filtered differently. Visibility
is security-relevant and must not be re-derived per interface.

## Decision

`KnowledgeItem.visible_to(user)` returns the base `Select` for everything a
viewer may read; `is_visible_to(user)` is the per-instance equivalent. All
listings, detail lookups, search filtering and API resolvers start from these
two methods. The search engine scores the full index and applies the policy
*after* scoring.

## Consequences

* A single, well-tested definition (anonymous → published public; user → plus
  own; admin → all).
* Collection statistics in the search index are not biased by the viewer.
* Any new read path must start from `visible_to`; reviewers can check this
  mechanically.

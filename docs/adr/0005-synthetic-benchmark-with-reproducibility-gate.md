# 0005 – Synthetic benchmark with a CI reproducibility gate

**Status:** Accepted · **Date:** 2026-10-03

## Context

Claims about ranking quality need evidence. Public test collections are
large, licensed and slow for CI, and offer no control over the properties
under study (morphology, length skew, stuffing).

## Decision

Generate a seeded synthetic collection with exact graded relevance
(`experiments/corpus.py`), evaluate with standard IR metrics plus bootstrap
confidence intervals and paired significance tests
(`app/search/metrics.py`), commit the results, and make CI re-run the
experiment and assert the committed aggregates reproduce exactly.

## Consequences

* Any change to the analyzer, index or rankers that alters effectiveness is
  visible in a pull request as a benchmark diff.
* Results are internally valid and controllable but not comparable with TREC
  numbers; `docs/RESEARCH.md` records this threat to validity.
* Experiments stay fast (seconds), so they run on every push.

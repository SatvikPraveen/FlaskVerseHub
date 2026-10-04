"""Offline retrieval evaluation metrics.

All functions take a ranked list of document ids and a relevance judgement
mapping ``doc_id -> grade`` (``grade > 0`` means relevant). Metrics follow
the definitions in Manning, Raghavan & Schütze, *Introduction to Information
Retrieval* (2008), ch. 8, and Järvelin & Kekäläinen (2002) for nDCG.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

import numpy as np

Qrels = Mapping[Any, float]


def _relevant(qrels: Qrels) -> set[Any]:
    return {doc for doc, grade in qrels.items() if grade > 0}


def precision_at_k(ranked: Sequence[Any], qrels: Qrels, k: int) -> float:
    if k <= 0:
        msg = "k must be positive"
        raise ValueError(msg)
    top = ranked[:k]
    relevant = _relevant(qrels)
    return sum(1 for doc in top if doc in relevant) / k


def recall_at_k(ranked: Sequence[Any], qrels: Qrels, k: int) -> float:
    relevant = _relevant(qrels)
    if not relevant:
        return 0.0
    return sum(1 for doc in ranked[:k] if doc in relevant) / len(relevant)


def reciprocal_rank(ranked: Sequence[Any], qrels: Qrels) -> float:
    relevant = _relevant(qrels)
    for position, doc in enumerate(ranked, start=1):
        if doc in relevant:
            return 1.0 / position
    return 0.0


def average_precision(ranked: Sequence[Any], qrels: Qrels, k: int | None = None) -> float:
    relevant = _relevant(qrels)
    if not relevant:
        return 0.0
    hits = 0
    total = 0.0
    for position, doc in enumerate(ranked[:k] if k else ranked, start=1):
        if doc in relevant:
            hits += 1
            total += hits / position
    return total / len(relevant)


def dcg_at_k(ranked: Sequence[Any], qrels: Qrels, k: int) -> float:
    gains = np.asarray([float(qrels.get(doc, 0.0)) for doc in ranked[:k]], dtype=np.float64)
    if gains.size == 0:
        return 0.0
    discounts = 1.0 / np.log2(np.arange(2, gains.size + 2))
    return float(np.sum((2.0**gains - 1.0) * discounts))


def ndcg_at_k(ranked: Sequence[Any], qrels: Qrels, k: int) -> float:
    ideal = sorted((grade for grade in qrels.values() if grade > 0), reverse=True)[:k]
    if not ideal:
        return 0.0
    ideal_dcg = dcg_at_k(list(range(len(ideal))), dict(enumerate(ideal)), k)
    return dcg_at_k(ranked, qrels, k) / ideal_dcg if ideal_dcg > 0 else 0.0


def f1_at_k(ranked: Sequence[Any], qrels: Qrels, k: int) -> float:
    p, r = precision_at_k(ranked, qrels, k), recall_at_k(ranked, qrels, k)
    return 2 * p * r / (p + r) if (p + r) else 0.0


METRICS: dict[str, Any] = {
    "P@5": lambda r, q: precision_at_k(r, q, 5),
    "P@10": lambda r, q: precision_at_k(r, q, 10),
    "R@10": lambda r, q: recall_at_k(r, q, 10),
    "F1@10": lambda r, q: f1_at_k(r, q, 10),
    "MRR": reciprocal_rank,
    "MAP": average_precision,
    "nDCG@10": lambda r, q: ndcg_at_k(r, q, 10),
}


GRADED_METRICS: frozenset[str] = frozenset({"nDCG@10"})
"""Metrics that consume graded judgements; all others are binary."""


def binarize(qrels: Qrels, threshold: float) -> dict[Any, float]:
    """Keep only judgements with ``grade >= threshold`` (TREC-style relevance cut-off)."""
    return {doc: grade for doc, grade in qrels.items() if grade >= threshold}


def evaluate_query(
    ranked: Sequence[Any],
    qrels: Qrels,
    metrics: Mapping[str, Any] = METRICS,
    *,
    binary_threshold: float = 1.0,
) -> dict[str, float]:
    """Score one ranking. Binary metrics see ``qrels`` cut at ``binary_threshold``."""
    binary = binarize(qrels, binary_threshold)
    return {
        name: float(fn(ranked, qrels if name in GRADED_METRICS else binary))
        for name, fn in metrics.items()
    }


@dataclass(frozen=True, slots=True)
class Summary:
    mean: float
    std: float
    ci_low: float
    ci_high: float
    n: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "mean": round(self.mean, 4),
            "std": round(self.std, 4),
            "ci95": [round(self.ci_low, 4), round(self.ci_high, 4)],
            "n": self.n,
        }


def bootstrap_summary(
    values: Sequence[float], *, resamples: int = 2000, seed: int = 0, alpha: float = 0.05
) -> Summary:
    """Mean with a percentile bootstrap confidence interval (deterministic for a seed)."""
    data = np.asarray(values, dtype=np.float64)
    if data.size == 0:
        return Summary(0.0, 0.0, 0.0, 0.0, 0)
    rng = np.random.default_rng(seed)
    samples = rng.choice(data, size=(resamples, data.size), replace=True).mean(axis=1)
    low, high = np.quantile(samples, [alpha / 2, 1 - alpha / 2])
    return Summary(
        mean=float(data.mean()),
        std=float(data.std(ddof=1)) if data.size > 1 else 0.0,
        ci_low=float(low),
        ci_high=float(high),
        n=int(data.size),
    )


def paired_bootstrap_pvalue(
    a: Sequence[float], b: Sequence[float], *, resamples: int = 5000, seed: int = 0
) -> float:
    """Two-sided paired bootstrap test that mean(a) != mean(b) over the same queries."""
    diff = np.asarray(a, dtype=np.float64) - np.asarray(b, dtype=np.float64)
    if diff.size == 0:
        return 1.0
    observed = abs(diff.mean())
    rng = np.random.default_rng(seed)
    centered = diff - diff.mean()
    samples = rng.choice(centered, size=(resamples, diff.size), replace=True).mean(axis=1)
    return float(np.mean(np.abs(samples) >= observed))


def evaluate_run(
    rankings: Mapping[Any, Sequence[Any]],
    judgements: Mapping[Any, Qrels],
    *,
    metrics: Mapping[str, Any] = METRICS,
    seed: int = 0,
    binary_threshold: float = 1.0,
) -> dict[str, Any]:
    """Evaluate a ``query_id -> ranked ids`` run against ``query_id -> qrels``."""
    per_query: dict[Any, dict[str, float]] = {}
    for query_id, qrels in judgements.items():
        per_query[query_id] = evaluate_query(
            rankings.get(query_id, []), qrels, metrics, binary_threshold=binary_threshold
        )
    aggregate = {
        name: bootstrap_summary(
            [scores[name] for scores in per_query.values()], seed=seed
        ).to_dict()
        for name in metrics
    }
    return {"per_query": per_query, "aggregate": aggregate, "queries": len(per_query)}


__all__ = [
    "GRADED_METRICS",
    "METRICS",
    "Summary",
    "average_precision",
    "binarize",
    "bootstrap_summary",
    "dcg_at_k",
    "evaluate_query",
    "evaluate_run",
    "f1_at_k",
    "ndcg_at_k",
    "paired_bootstrap_pvalue",
    "precision_at_k",
    "recall_at_k",
    "reciprocal_rank",
]

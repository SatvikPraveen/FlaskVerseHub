"""Ranking functions over an :class:`~app.search.index.InvertedIndex`.

Each ranker maps a bag of query terms to a score vector over every document
in the index. Implementations are vectorised with NumPy over posting lists.

References
----------
* Robertson, S. E., Walker, S., Jones, S., Hancock-Beaulieu, M. & Gatford, M.
  (1994). *Okapi at TREC-3*. - BM25.
* Lv, Y. & Zhai, C. (2011). *Lower-bounding term frequency normalization*.
  CIKM. - BM25+.
* Salton, G. & Buckley, C. (1988). *Term-weighting approaches in automatic
  text retrieval*. - TF-IDF / vector space model.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

import numpy as np
from numpy.typing import NDArray

from app.search.index import InvertedIndex


@dataclass(frozen=True, slots=True)
class TermContribution:
    term: str
    tf: float
    df: int
    idf: float
    weight: float


class Ranker(ABC):
    """Base class: subclasses implement :meth:`idf` and :meth:`term_weights`."""

    name: str = "ranker"

    @abstractmethod
    def idf(self, index: InvertedIndex, term: str) -> float:
        """Return the inverse document frequency of ``term`` in ``index``."""

    @abstractmethod
    def term_weights(
        self, index: InvertedIndex, term: str, qtf: int
    ) -> tuple[NDArray[np.int64], NDArray[np.float64]]:
        """Return ``(doc_positions, weights)`` for one query term."""

    def score(self, index: InvertedIndex, query_terms: Sequence[str]) -> NDArray[np.float64]:
        scores = np.zeros(index.num_docs, dtype=np.float64)
        for term, qtf in Counter(query_terms).items():
            if term not in index:
                continue
            positions, weights = self.term_weights(index, term, qtf)
            np.add.at(scores, positions, weights)
        return self.finalize(index, query_terms, scores)

    def finalize(
        self,
        index: InvertedIndex,  # noqa: ARG002 - hook signature used by subclasses
        query_terms: Sequence[str],  # noqa: ARG002
        scores: NDArray[np.float64],
    ) -> NDArray[np.float64]:
        """Hook for post-processing (e.g. cosine normalisation)."""
        return scores

    def explain(
        self, index: InvertedIndex, query_terms: Sequence[str], position: int
    ) -> list[TermContribution]:
        """Per-term contributions to the score of the document at ``position``."""
        out: list[TermContribution] = []
        vector = index.term_vector(position)
        for term, qtf in Counter(query_terms).items():
            if term not in index or term not in vector:
                continue
            positions, weights = self.term_weights(index, term, qtf)
            match = np.nonzero(positions == position)[0]
            if match.size:
                out.append(
                    TermContribution(
                        term=term,
                        tf=float(vector[term]),
                        df=index.df(term),
                        idf=float(self.idf(index, term)),
                        weight=float(weights[match[0]]),
                    )
                )
        return sorted(out, key=lambda c: c.weight, reverse=True)

    def params(self) -> dict[str, Any]:
        return {}

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({self.params()})"


class BM25Ranker(Ranker):
    """Okapi BM25 with the standard (non-negative) IDF formulation."""

    name = "bm25"

    def __init__(self, k1: float = 1.5, b: float = 0.75) -> None:
        if k1 < 0 or not 0 <= b <= 1:
            msg = "k1 must be >= 0 and b in [0, 1]"
            raise ValueError(msg)
        self.k1 = k1
        self.b = b

    def idf(self, index: InvertedIndex, term: str) -> float:
        n, df = index.num_docs, index.df(term)
        return float(np.log(1.0 + (n - df + 0.5) / (df + 0.5)))

    def _norm(self, index: InvertedIndex, positions: NDArray[np.int64]) -> NDArray[np.float64]:
        avg = index.avg_doc_length or 1.0
        return 1.0 - self.b + self.b * index.doc_lengths[positions] / avg

    def term_weights(
        self, index: InvertedIndex, term: str, qtf: int
    ) -> tuple[NDArray[np.int64], NDArray[np.float64]]:
        posting = index.postings[term]
        tf = posting.term_freqs
        norm = self._norm(index, posting.doc_indices)
        saturation = tf * (self.k1 + 1.0) / (tf + self.k1 * norm)
        return posting.doc_indices, qtf * self.idf(index, term) * saturation

    def params(self) -> dict[str, Any]:
        return {"k1": self.k1, "b": self.b}


class BM25PlusRanker(BM25Ranker):
    """BM25+ (Lv & Zhai 2011): adds a lower bound ``delta`` to term frequency saturation."""

    name = "bm25plus"

    def __init__(self, k1: float = 1.5, b: float = 0.75, delta: float = 1.0) -> None:
        super().__init__(k1, b)
        if delta < 0:
            msg = "delta must be >= 0"
            raise ValueError(msg)
        self.delta = delta

    def term_weights(
        self, index: InvertedIndex, term: str, qtf: int
    ) -> tuple[NDArray[np.int64], NDArray[np.float64]]:
        posting = index.postings[term]
        tf = posting.term_freqs
        norm = self._norm(index, posting.doc_indices)
        saturation = tf * (self.k1 + 1.0) / (tf + self.k1 * norm) + self.delta
        return posting.doc_indices, qtf * self.idf(index, term) * saturation

    def params(self) -> dict[str, Any]:
        return {**super().params(), "delta": self.delta}


class TFIDFRanker(Ranker):
    """Vector-space cosine similarity with ``lnc.ltc`` weighting (SMART notation).

    Documents use log tf with cosine normalisation; queries use log tf * idf.
    """

    name = "tfidf"

    def __init__(self, *, sublinear_tf: bool = True) -> None:
        self.sublinear_tf = sublinear_tf
        self._norm_cache: dict[int, NDArray[np.float64]] = {}

    def idf(self, index: InvertedIndex, term: str) -> float:
        df = index.df(term)
        return float(np.log(index.num_docs / df)) if df else 0.0

    def _tf(self, tf: NDArray[np.float64]) -> NDArray[np.float64]:
        return (
            np.where(tf > 0, 1.0 + np.log(np.maximum(tf, 1e-12)), 0.0) if self.sublinear_tf else tf
        )

    def _doc_norms(self, index: InvertedIndex) -> NDArray[np.float64]:
        key = id(index)
        cached = self._norm_cache.get(key)
        if cached is not None and cached.size == index.num_docs:
            return cached
        norms = np.zeros(index.num_docs, dtype=np.float64)
        for posting in index.postings.values():
            np.add.at(norms, posting.doc_indices, self._tf(posting.term_freqs) ** 2)
        norms = np.sqrt(norms)
        norms[norms == 0] = 1.0
        self._norm_cache = {key: norms}
        return norms

    def term_weights(
        self, index: InvertedIndex, term: str, qtf: int
    ) -> tuple[NDArray[np.int64], NDArray[np.float64]]:
        posting = index.postings[term]
        query_weight = (1.0 + np.log(qtf)) * self.idf(index, term)
        doc_weights = self._tf(posting.term_freqs) / self._doc_norms(index)[posting.doc_indices]
        return posting.doc_indices, query_weight * doc_weights

    def finalize(
        self, index: InvertedIndex, query_terms: Sequence[str], scores: NDArray[np.float64]
    ) -> NDArray[np.float64]:
        query_norm = 0.0
        for term, qtf in Counter(query_terms).items():
            if term in index:
                query_norm += ((1.0 + np.log(qtf)) * self.idf(index, term)) ** 2
        return scores / np.sqrt(query_norm) if query_norm > 0 else scores

    def params(self) -> dict[str, Any]:
        return {"sublinear_tf": self.sublinear_tf}


RANKERS: dict[str, type[Ranker]] = {
    BM25Ranker.name: BM25Ranker,
    BM25PlusRanker.name: BM25PlusRanker,
    TFIDFRanker.name: TFIDFRanker,
}


def get_ranker(name: str, **params: Any) -> Ranker:
    try:
        cls = RANKERS[name.lower()]
    except KeyError as exc:
        msg = f"unknown ranker {name!r}; choose from {sorted(RANKERS)}"
        raise ValueError(msg) from exc
    return cls(**params)


__all__ = [
    "RANKERS",
    "BM25PlusRanker",
    "BM25Ranker",
    "Ranker",
    "TFIDFRanker",
    "TermContribution",
    "get_ranker",
]

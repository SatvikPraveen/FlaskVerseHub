"""``SearchEngine``: analyzer + index + ranker with a small query API."""

from __future__ import annotations

import time
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

import numpy as np
from numpy.typing import NDArray

from app.search.analysis import Analyzer
from app.search.index import Document, InvertedIndex
from app.search.rankers import Ranker, TermContribution, get_ranker

DEFAULT_FIELD_BOOSTS: Mapping[str, float] = {
    "title": 3.0,
    "summary": 2.0,
    "tags": 2.0,
    "content": 1.0,
}


@dataclass(frozen=True, slots=True)
class SearchHit:
    doc_id: Any
    score: float
    rank: int
    metadata: Mapping[str, Any]


@dataclass(frozen=True, slots=True)
class SearchResult:
    query: str
    terms: list[str]
    hits: list[SearchHit]
    total: int
    elapsed_ms: float
    ranker: str


class SearchEngine:
    def __init__(
        self,
        documents: Iterable[Document] = (),
        *,
        analyzer: Analyzer | None = None,
        ranker: Ranker | str = "bm25",
        field_boosts: Mapping[str, float] | None = None,
        ranker_params: Mapping[str, Any] | None = None,
    ) -> None:
        self.analyzer = analyzer or Analyzer()
        self.ranker: Ranker = (
            get_ranker(ranker, **dict(ranker_params or {})) if isinstance(ranker, str) else ranker
        )
        self.index = InvertedIndex.build(
            documents, self.analyzer, field_boosts=field_boosts or DEFAULT_FIELD_BOOSTS
        )

    # -- querying -----------------------------------------------------------
    def analyze_query(self, query: str) -> list[str]:
        return self.analyzer.analyze(query)

    def scores(self, query: str) -> NDArray[np.float64]:
        return self.ranker.score(self.index, self.analyze_query(query))

    def search(
        self,
        query: str,
        *,
        k: int | None = 10,
        offset: int = 0,
        min_score: float = 0.0,
        allowed_doc_ids: set[Any] | None = None,
    ) -> SearchResult:
        """Rank every document for ``query`` and return hits ``offset:offset+k``.

        ``allowed_doc_ids`` filters results *after* scoring so corpus
        statistics (IDF, average length) are not distorted by the filter.
        """
        started = time.perf_counter()
        terms = self.analyze_query(query)
        scores = self.ranker.score(self.index, terms) if terms else np.zeros(self.index.num_docs)
        order = np.argsort(-scores, kind="stable")
        hits: list[SearchHit] = []
        rank = 0
        for position in order:
            score = float(scores[position])
            if score <= min_score:
                break
            doc_id = self.index.doc_ids[position]
            if allowed_doc_ids is not None and doc_id not in allowed_doc_ids:
                continue
            rank += 1
            hits.append(SearchHit(doc_id, score, rank, self.index.metadata[position]))
        total = len(hits)
        page = hits[offset : offset + k] if k is not None else hits[offset:]
        return SearchResult(
            query=query,
            terms=terms,
            hits=page,
            total=total,
            elapsed_ms=round((time.perf_counter() - started) * 1000, 3),
            ranker=self.ranker.name,
        )

    def explain(self, query: str, doc_id: Any) -> list[TermContribution]:
        position = self.index.position_of(doc_id)
        if position is None:
            return []
        return self.ranker.explain(self.index, self.analyze_query(query), position)

    def suggest(self, prefix: str, *, limit: int = 8) -> list[str]:
        """Vocabulary terms starting with ``prefix`` ordered by collection frequency."""
        needle = prefix.strip().lower()
        if not needle:
            return []
        stem = self.analyzer.analyze(needle)
        candidates = [
            t
            for t in self.index.vocabulary
            if t.startswith(needle) or (stem and t.startswith(stem[0]))
        ]
        candidates.sort(key=lambda t: (-self.index.total_term_frequency(t), t))
        return candidates[:limit]

    def ranked_ids(self, query: str, *, k: int | None = None) -> Sequence[Any]:
        return [hit.doc_id for hit in self.search(query, k=k).hits]

    def stats(self) -> dict[str, Any]:
        return {
            **self.index.stats(),
            "ranker": self.ranker.name,
            "ranker_params": self.ranker.params(),
        }


__all__ = ["DEFAULT_FIELD_BOOSTS", "SearchEngine", "SearchHit", "SearchResult"]

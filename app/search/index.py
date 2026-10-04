"""In-memory inverted index with per-document statistics."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

import numpy as np
from numpy.typing import NDArray

from app.search.analysis import Analyzer


@dataclass(frozen=True, slots=True)
class Document:
    """A unit of retrieval. ``fields`` are indexed with the given boosts."""

    doc_id: Any
    fields: Mapping[str, str | None]
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class Posting:
    """Term occurrences for one term: parallel arrays of doc positions and tfs."""

    doc_indices: NDArray[np.int64]
    term_freqs: NDArray[np.float64]

    @property
    def df(self) -> int:
        return int(self.doc_indices.size)


class InvertedIndex:
    """Term -> posting list, plus document lengths and corpus statistics.

    Field boosts are applied by weighting term frequencies: a term that occurs
    once in a field with boost 3.0 contributes ``tf = 3.0``. Document length
    is the boosted token count so BM25 length normalisation stays consistent.
    """

    def __init__(
        self,
        analyzer: Analyzer | None = None,
        *,
        field_boosts: Mapping[str, float] | None = None,
    ) -> None:
        self.analyzer = analyzer or Analyzer()
        self.field_boosts: dict[str, float] = dict(field_boosts or {})
        self.doc_ids: list[Any] = []
        self.metadata: list[Mapping[str, Any]] = []
        self.doc_lengths: NDArray[np.float64] = np.zeros(0, dtype=np.float64)
        self.postings: dict[str, Posting] = {}
        self._term_counts: dict[str, int] = {}
        self._vocab_doc_freq: dict[str, int] = {}
        self._term_vectors: list[dict[str, float]] = []

    # -- construction -------------------------------------------------------
    @classmethod
    def build(
        cls,
        documents: Iterable[Document],
        analyzer: Analyzer | None = None,
        *,
        field_boosts: Mapping[str, float] | None = None,
    ) -> InvertedIndex:
        index = cls(analyzer, field_boosts=field_boosts)
        index.add_documents(documents)
        return index

    def add_documents(self, documents: Iterable[Document]) -> None:
        temp: dict[str, list[tuple[int, float]]] = defaultdict(list)
        lengths: list[float] = list(self.doc_lengths)
        for existing_term, posting in self.postings.items():
            temp[existing_term].extend(
                zip(posting.doc_indices.tolist(), posting.term_freqs.tolist(), strict=True)
            )

        for document in documents:
            position = len(self.doc_ids)
            self.doc_ids.append(document.doc_id)
            self.metadata.append(document.metadata)
            weights: dict[str, float] = defaultdict(float)
            length = 0.0
            for name, text in document.fields.items():
                boost = float(self.field_boosts.get(name, 1.0))
                terms = self.analyzer.analyze(text)
                length += boost * len(terms)
                for term in terms:
                    weights[term] += boost
            lengths.append(length)
            self._term_vectors.append(dict(weights))
            for term, tf in weights.items():
                temp[term].append((position, tf))

        self.doc_lengths = np.asarray(lengths, dtype=np.float64)
        self.postings = {
            term: Posting(
                doc_indices=np.asarray([d for d, _ in entries], dtype=np.int64),
                term_freqs=np.asarray([tf for _, tf in entries], dtype=np.float64),
            )
            for term, entries in temp.items()
        }
        self._vocab_doc_freq = {term: posting.df for term, posting in self.postings.items()}
        self._term_counts = {
            term: int(posting.term_freqs.sum()) for term, posting in self.postings.items()
        }

    # -- statistics ---------------------------------------------------------
    @property
    def num_docs(self) -> int:
        return len(self.doc_ids)

    @property
    def avg_doc_length(self) -> float:
        return float(self.doc_lengths.mean()) if self.num_docs else 0.0

    @property
    def vocabulary(self) -> Sequence[str]:
        return list(self.postings)

    def df(self, term: str) -> int:
        return self._vocab_doc_freq.get(term, 0)

    def total_term_frequency(self, term: str) -> int:
        return self._term_counts.get(term, 0)

    def term_vector(self, position: int) -> Mapping[str, float]:
        return self._term_vectors[position]

    def position_of(self, doc_id: Any) -> int | None:
        try:
            return self.doc_ids.index(doc_id)
        except ValueError:
            return None

    def __len__(self) -> int:
        return self.num_docs

    def __contains__(self, term: object) -> bool:
        return term in self.postings

    def stats(self) -> dict[str, Any]:
        return {
            "documents": self.num_docs,
            "vocabulary": len(self.postings),
            "avg_doc_length": round(self.avg_doc_length, 2),
            "postings": int(sum(p.df for p in self.postings.values())),
            "analyzer": self.analyzer.name,
            "field_boosts": self.field_boosts,
        }


__all__ = ["Document", "InvertedIndex", "Posting"]

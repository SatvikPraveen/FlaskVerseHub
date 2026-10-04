"""Information-retrieval engine.

A self-contained, dependency-light search stack implemented from first
principles so that every ranking decision is inspectable and reproducible:

* :mod:`app.search.analysis`  - tokenisation, stop-word removal, Porter stemming
* :mod:`app.search.index`     - in-memory inverted index with document statistics
* :mod:`app.search.rankers`   - BM25, BM25+ and TF-IDF cosine ranking functions
* :mod:`app.search.engine`    - composes the above into ``SearchEngine``
* :mod:`app.search.metrics`   - offline evaluation (P@k, R@k, AP/MAP, nDCG, MRR) with
  bootstrap confidence intervals
* :mod:`app.search.service`   - Flask integration over knowledge items
"""

from app.search.analysis import Analyzer
from app.search.engine import SearchEngine, SearchHit
from app.search.index import Document, InvertedIndex
from app.search.rankers import BM25PlusRanker, BM25Ranker, Ranker, TFIDFRanker, get_ranker

__all__ = [
    "Analyzer",
    "BM25PlusRanker",
    "BM25Ranker",
    "Document",
    "InvertedIndex",
    "Ranker",
    "SearchEngine",
    "SearchHit",
    "TFIDFRanker",
    "get_ranker",
]

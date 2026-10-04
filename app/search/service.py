"""Flask integration: search knowledge items with the retrieval engine.

The engine indexes *every* item so collection statistics are stable, then
filters hits by the viewer's visibility set. The index is rebuilt lazily when
items change (tracked by a cheap ``max(updated_at), count`` fingerprint) or
after ``SEARCH_INDEX_TTL_SECONDS``.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from typing import Any

from flask import Flask, current_app
from sqlalchemy import func, select

from app.extensions import db
from app.models import KnowledgeItem, User
from app.search.analysis import Analyzer
from app.search.engine import SearchEngine, SearchResult
from app.search.index import Document
from app.search.rankers import TermContribution
from app.utils.pagination import Page


@dataclass(frozen=True, slots=True)
class SearchPage(Page[KnowledgeItem]):
    """A :class:`Page` of items plus retrieval diagnostics."""

    scores: dict[int, float]
    terms: list[str]
    ranker: str
    elapsed_ms: float

    def to_dict(self) -> dict[str, Any]:
        # Zero-argument super() is unavailable in slots dataclasses; call the base explicitly.
        return {
            **Page.to_dict(self),
            "ranker": self.ranker,
            "terms": self.terms,
            "elapsed_ms": self.elapsed_ms,
        }


class _EngineCache:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._engine: SearchEngine | None = None
        self._fingerprint: tuple[Any, ...] | None = None
        self._built_at = 0.0

    def _fingerprint_now(self) -> tuple[Any, ...]:
        row = db.session.execute(
            select(func.count(KnowledgeItem.id), func.max(KnowledgeItem.updated_at))
        ).one()
        return (int(row[0] or 0), str(row[1]))

    def get(self) -> SearchEngine:
        ttl = float(current_app.config.get("SEARCH_INDEX_TTL_SECONDS", 60))
        now = time.monotonic()
        with self._lock:
            fresh = self._engine is not None and (now - self._built_at) < ttl
            if fresh and self._engine is not None:
                return self._engine
            fingerprint = self._fingerprint_now()
            if self._engine is not None and fingerprint == self._fingerprint:
                self._built_at = now
                return self._engine
            self._engine = build_engine()
            self._fingerprint = fingerprint
            self._built_at = now
            return self._engine

    def invalidate(self) -> None:
        with self._lock:
            self._engine = None
            self._fingerprint = None


_cache = _EngineCache()


def _documents() -> list[Document]:
    items = db.session.scalars(select(KnowledgeItem)).all()
    return [
        Document(
            doc_id=item.id,
            fields={
                "title": item.title,
                "summary": item.summary,
                "tags": " ".join(item.tag_names),
                "content": item.content,
            },
            metadata={"slug": item.slug, "title": item.title},
        )
        for item in items
    ]


def build_engine() -> SearchEngine:
    config = current_app.config
    ranker = str(config.get("SEARCH_RANKER", "bm25"))
    params: dict[str, Any] = {}
    if ranker.startswith("bm25"):
        params = {
            "k1": float(config.get("SEARCH_BM25_K1", 1.5)),
            "b": float(config.get("SEARCH_BM25_B", 0.75)),
        }
    return SearchEngine(_documents(), analyzer=Analyzer(), ranker=ranker, ranker_params=params)


def get_engine() -> SearchEngine:
    return _cache.get()


def invalidate() -> None:
    _cache.invalidate()


def _visible_ids(user: User | None) -> set[int]:
    visible = KnowledgeItem.visible_to(user).subquery()
    return set(db.session.scalars(select(visible.c.id)).all())


def search_items(query: str, *, user: User | None, page: int = 1, per_page: int = 20) -> SearchPage:
    """Rank visible items for ``query`` and return one page, preserving rank order."""
    engine = get_engine()
    allowed = _visible_ids(user)
    result: SearchResult = engine.search(
        query, k=per_page, offset=(page - 1) * per_page, allowed_doc_ids=allowed
    )
    ids = [hit.doc_id for hit in result.hits]
    by_id = {
        item.id: item
        for item in db.session.scalars(
            select(KnowledgeItem).where(KnowledgeItem.id.in_(ids or [0]))
        ).all()
    }
    items = [by_id[i] for i in ids if i in by_id]
    return SearchPage(
        items=items,
        page=page,
        per_page=per_page,
        total=result.total,
        scores={hit.doc_id: round(hit.score, 4) for hit in result.hits},
        terms=result.terms,
        ranker=result.ranker,
        elapsed_ms=result.elapsed_ms,
    )


def explain(query: str, item: KnowledgeItem) -> list[TermContribution]:
    return get_engine().explain(query, item.id)


def suggest(prefix: str, *, limit: int = 8) -> list[str]:
    return get_engine().suggest(prefix, limit=limit)


def init_app(_app: Flask) -> None:
    """Invalidate the cached index whenever a knowledge item changes."""
    from sqlalchemy import event

    @event.listens_for(db.session.__class__, "after_commit")
    def _after_commit(session: Any) -> None:  # pragma: no cover - thin hook
        if any(isinstance(obj, KnowledgeItem) for obj in session.info.get("touched", ())):
            _cache.invalidate()

    @event.listens_for(db.session.__class__, "before_flush")
    def _before_flush(session: Any, _ctx: Any, _instances: Any) -> None:
        touched = [
            o for o in session.new | session.dirty | session.deleted if isinstance(o, KnowledgeItem)
        ]
        if touched:
            session.info.setdefault("touched", set()).update(touched)
            _cache.invalidate()


__all__ = [
    "SearchPage",
    "build_engine",
    "explain",
    "get_engine",
    "init_app",
    "invalidate",
    "search_items",
    "suggest",
]

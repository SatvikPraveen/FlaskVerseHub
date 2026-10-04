"""Backend-agnostic pagination over SQLAlchemy 2.0 ``Select`` statements."""

from __future__ import annotations

from dataclasses import dataclass
from math import ceil
from typing import Any, Generic, TypeVar

from flask import current_app, request
from sqlalchemy import func, select
from sqlalchemy.sql import Select

from app.extensions import db

T = TypeVar("T")


@dataclass(frozen=True, slots=True)
class Page(Generic[T]):
    items: list[T]
    page: int
    per_page: int
    total: int

    @property
    def pages(self) -> int:
        return max(1, ceil(self.total / self.per_page)) if self.per_page else 1

    @property
    def has_prev(self) -> bool:
        return self.page > 1

    @property
    def has_next(self) -> bool:
        return self.page < self.pages

    @property
    def prev_num(self) -> int | None:
        return self.page - 1 if self.has_prev else None

    @property
    def next_num(self) -> int | None:
        return self.page + 1 if self.has_next else None

    @property
    def first_index(self) -> int:
        return 0 if self.total == 0 else (self.page - 1) * self.per_page + 1

    @property
    def last_index(self) -> int:
        return min(self.page * self.per_page, self.total)

    def iter_pages(self, *, edge: int = 1, around: int = 2) -> list[int | None]:
        """Page numbers with ``None`` gaps, e.g. ``[1, None, 4, 5, 6, None, 20]``."""
        result: list[int | None] = []
        last = 0
        for number in range(1, self.pages + 1):
            keep = number <= edge or number > self.pages - edge or abs(number - self.page) <= around
            if keep:
                if last and number - last > 1:
                    result.append(None)
                result.append(number)
                last = number
        return result

    def to_dict(self) -> dict[str, Any]:
        return {
            "page": self.page,
            "per_page": self.per_page,
            "total": self.total,
            "pages": self.pages,
            "has_next": self.has_next,
            "has_prev": self.has_prev,
        }


def page_args(default_per_page: int | None = None) -> tuple[int, int]:
    """Read and clamp ``page``/``per_page`` from the current request."""
    max_per_page = int(current_app.config.get("MAX_ITEMS_PER_PAGE", 100))
    fallback = default_per_page or int(current_app.config.get("ITEMS_PER_PAGE", 20))
    page = max(1, request.args.get("page", 1, type=int) or 1)
    per_page = request.args.get("per_page", fallback, type=int) or fallback
    return page, max(1, min(per_page, max_per_page))


def paginate(stmt: Select[T], page: int, per_page: int) -> Page[T]:
    """Execute ``stmt`` for one page and compute the total with a wrapped count."""
    total = db.session.scalar(select(func.count()).select_from(stmt.order_by(None).subquery()))
    items = list(db.session.scalars(stmt.offset((page - 1) * per_page).limit(per_page)).all())
    return Page(items=items, page=page, per_page=per_page, total=int(total or 0))


__all__ = ["Page", "page_args", "paginate"]

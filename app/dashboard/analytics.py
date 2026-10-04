"""Analytics queries for the dashboards.

Every function returns plain dictionaries/lists so results can be rendered
in templates, serialised for Chart.js, or asserted in tests.
"""

from __future__ import annotations

import statistics
from collections.abc import Sequence
from datetime import timedelta
from typing import Any

from sqlalchemy import func, select

from app.extensions import db
from app.models import (
    Activity,
    Bookmark,
    Category,
    Comment,
    Difficulty,
    ItemStatus,
    KnowledgeItem,
    Tag,
    User,
    knowledge_item_tags,
)
from app.utils.time import utcnow


def _count(stmt: Any) -> int:
    return int(db.session.scalar(select(func.count()).select_from(stmt.subquery())) or 0)


def overview() -> dict[str, int]:
    return {
        "users": int(db.session.scalar(select(func.count(User.id))) or 0),
        "items": int(db.session.scalar(select(func.count(KnowledgeItem.id))) or 0),
        "public_items": _count(select(KnowledgeItem.id).where(KnowledgeItem.is_public.is_(True))),
        "categories": int(db.session.scalar(select(func.count(Category.id))) or 0),
        "tags": int(db.session.scalar(select(func.count(Tag.id))) or 0),
        "comments": int(db.session.scalar(select(func.count(Comment.id))) or 0),
        "bookmarks": int(db.session.scalar(select(func.count(Bookmark.id))) or 0),
        "views": int(
            db.session.scalar(select(func.coalesce(func.sum(KnowledgeItem.view_count), 0))) or 0
        ),
    }


def items_per_day(days: int = 30) -> list[dict[str, Any]]:
    """Items created per calendar day over the trailing window (zero-filled)."""
    start = (utcnow() - timedelta(days=days - 1)).replace(hour=0, minute=0, second=0, microsecond=0)
    rows = db.session.execute(
        select(KnowledgeItem.created_at).where(KnowledgeItem.created_at >= start)
    ).all()
    buckets = {(start + timedelta(days=i)).date().isoformat(): 0 for i in range(days)}
    for (created_at,) in rows:
        key = created_at.date().isoformat()
        if key in buckets:
            buckets[key] += 1
    return [{"date": day, "count": count} for day, count in buckets.items()]


def status_distribution() -> dict[str, int]:
    rows = db.session.execute(
        select(KnowledgeItem.status, func.count(KnowledgeItem.id)).group_by(KnowledgeItem.status)
    ).all()
    found = {status.value: int(count) for status, count in rows}
    return {status.value: found.get(status.value, 0) for status in ItemStatus}


def difficulty_distribution() -> dict[str, int]:
    rows = db.session.execute(
        select(KnowledgeItem.difficulty, func.count(KnowledgeItem.id)).group_by(
            KnowledgeItem.difficulty
        )
    ).all()
    found = {difficulty.value: int(count) for difficulty, count in rows}
    return {d.value: found.get(d.value, 0) for d in Difficulty}


def items_by_category(limit: int = 10) -> list[dict[str, Any]]:
    rows = db.session.execute(
        select(Category.name, Category.color, func.count(KnowledgeItem.id).label("n"))
        .outerjoin(KnowledgeItem, KnowledgeItem.category_id == Category.id)
        .group_by(Category.id)
        .order_by(func.count(KnowledgeItem.id).desc(), Category.name)
        .limit(limit)
    ).all()
    return [{"name": name, "color": color, "count": int(n)} for name, color, n in rows]


def top_tags(limit: int = 15) -> list[dict[str, Any]]:
    rows = db.session.execute(
        select(Tag.name, func.count(knowledge_item_tags.c.item_id).label("n"))
        .join(knowledge_item_tags, knowledge_item_tags.c.tag_id == Tag.id)
        .group_by(Tag.id)
        .order_by(func.count(knowledge_item_tags.c.item_id).desc(), Tag.name)
        .limit(limit)
    ).all()
    return [{"name": name, "count": int(n)} for name, n in rows]


def top_authors(limit: int = 10) -> list[dict[str, Any]]:
    rows = db.session.execute(
        select(
            User.username,
            func.count(KnowledgeItem.id).label("n"),
            func.coalesce(func.sum(KnowledgeItem.view_count), 0),
        )
        .join(KnowledgeItem, KnowledgeItem.author_id == User.id)
        .group_by(User.id)
        .order_by(func.count(KnowledgeItem.id).desc(), User.username)
        .limit(limit)
    ).all()
    return [{"username": u, "items": int(n), "views": int(v)} for u, n, v in rows]


def most_viewed(limit: int = 10, *, user: User | None = None) -> Sequence[KnowledgeItem]:
    stmt = (
        KnowledgeItem.visible_to(user)
        .order_by(KnowledgeItem.view_count.desc(), KnowledgeItem.id)
        .limit(limit)
    )
    return db.session.scalars(stmt).all()


def reading_time_summary() -> dict[str, float]:
    """Descriptive statistics of estimated reading time (minutes) across items."""
    contents = db.session.scalars(select(KnowledgeItem.content)).all()
    from app.utils.text import reading_time_minutes

    values = [reading_time_minutes(c) for c in contents]
    if not values:
        return {"count": 0, "mean": 0.0, "median": 0.0, "p90": 0.0, "max": 0.0}
    ordered = sorted(values)
    p90 = ordered[min(len(ordered) - 1, round(0.9 * (len(ordered) - 1)))]
    return {
        "count": len(values),
        "mean": round(statistics.fmean(values), 2),
        "median": float(statistics.median(values)),
        "p90": float(p90),
        "max": float(ordered[-1]),
    }


def view_concentration() -> float:
    """Gini coefficient of view counts.

    0 means views are spread evenly; the finite-sample maximum ``(n - 1) / n``
    means a single item holds every view.
    """
    views = sorted(int(v) for v in db.session.scalars(select(KnowledgeItem.view_count)).all())
    n = len(views)
    total = sum(views)
    if n == 0 or total == 0:
        return 0.0
    cumulative = sum((i + 1) * v for i, v in enumerate(views))
    return round((2 * cumulative) / (n * total) - (n + 1) / n, 4)


def activity_breakdown(days: int = 7) -> list[dict[str, Any]]:
    since = utcnow() - timedelta(days=days)
    rows = db.session.execute(
        select(Activity.action, func.count(Activity.id))
        .where(Activity.created_at >= since)
        .group_by(Activity.action)
        .order_by(func.count(Activity.id).desc())
    ).all()
    return [{"action": action, "count": int(n)} for action, n in rows]


def recent_activity(limit: int = 20, *, user: User | None = None) -> Sequence[Activity]:
    stmt = select(Activity).order_by(Activity.created_at.desc()).limit(limit)
    if user is not None:
        stmt = stmt.where(Activity.user_id == user.id)
    return db.session.scalars(stmt).all()


def user_summary(user: User) -> dict[str, Any]:
    items = user.knowledge_items
    return {
        "items": items.count(),
        "public_items": items.filter(KnowledgeItem.is_public.is_(True)).count(),
        "views": int(
            db.session.scalar(
                select(func.coalesce(func.sum(KnowledgeItem.view_count), 0)).where(
                    KnowledgeItem.author_id == user.id
                )
            )
            or 0
        ),
        "comments": user.comments.count(),
        "bookmarks": user.bookmarks.count(),
        "unread_notifications": user.notifications.filter_by(is_read=False).count(),
    }


def admin_metrics() -> dict[str, Any]:
    """Everything the admin analytics page and its JSON endpoint need."""
    return {
        "overview": overview(),
        "items_per_day": items_per_day(),
        "status": status_distribution(),
        "difficulty": difficulty_distribution(),
        "categories": items_by_category(),
        "tags": top_tags(),
        "authors": top_authors(),
        "reading_time": reading_time_summary(),
        "view_gini": view_concentration(),
        "activity": activity_breakdown(),
        "generated_at": utcnow().isoformat(),
    }


__all__ = [
    "activity_breakdown",
    "admin_metrics",
    "difficulty_distribution",
    "items_by_category",
    "items_per_day",
    "most_viewed",
    "overview",
    "reading_time_summary",
    "recent_activity",
    "status_distribution",
    "top_authors",
    "top_tags",
    "user_summary",
    "view_concentration",
]

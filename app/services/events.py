"""Real-time domain events published over Socket.IO.

Called from the service layer so every interface (HTML, REST, GraphQL)
produces identical events.
"""

from __future__ import annotations

from typing import Any

from app.extensions import socketio
from app.models import Comment, KnowledgeItem
from app.utils.time import utcnow


def _payload(item: KnowledgeItem, **extra: Any) -> dict[str, Any]:
    return {
        "id": item.id,
        "slug": item.slug,
        "title": item.title,
        "author": item.author.username,
        "version": item.version,
        "at": utcnow().isoformat(),
        **extra,
    }


def item_created(item: KnowledgeItem) -> None:
    if item.is_public and item.is_published:
        socketio.emit("item:created", _payload(item), to="public")


def item_updated(item: KnowledgeItem, *, actor: str) -> None:
    payload = _payload(item, actor=actor)
    socketio.emit("item:updated", payload, to=f"item:{item.slug}")
    if item.is_public and item.is_published:
        socketio.emit("item:updated", payload, to="public")


def item_deleted(slug: str, title: str) -> None:
    payload = {"slug": slug, "title": title, "at": utcnow().isoformat()}
    socketio.emit("item:deleted", payload, to="public")
    socketio.emit("item:deleted", payload, to=f"item:{slug}")


def comment_added(comment: Comment) -> None:
    socketio.emit("comment:added", comment.to_dict(), to=f"item:{comment.item.slug}")


__all__ = ["comment_added", "item_created", "item_deleted", "item_updated"]

"""Knowledge item use-cases shared by the HTML, REST and GraphQL interfaces."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.sql import Select

from app.extensions import db
from app.models import (
    Bookmark,
    Category,
    Comment,
    Difficulty,
    ItemStatus,
    KnowledgeItem,
    KnowledgeItemRevision,
    NotificationKind,
    Tag,
    User,
)
from app.security.sanitization import sanitize_html, sanitize_text
from app.services import events
from app.services.activity import record_activity
from app.services.notifications import notify

SORT_OPTIONS: dict[str, Any] = {
    "updated": KnowledgeItem.updated_at.desc(),
    "created": KnowledgeItem.created_at.desc(),
    "title": KnowledgeItem.title.asc(),
    "views": KnowledgeItem.view_count.desc(),
    "likes": KnowledgeItem.like_count.desc(),
}


class PermissionDeniedError(PermissionError):
    """The acting user may not perform this operation."""


@dataclass(slots=True)
class ItemFilters:
    query: str | None = None
    category: str | None = None  # slug
    tag: str | None = None  # slug
    difficulty: str | None = None
    status: str | None = None
    mine: bool = False
    featured: bool | None = None
    sort: str = "updated"
    extra: dict[str, Any] = field(default_factory=dict)

    @staticmethod
    def _flag(value: Any) -> bool:
        return str(value or "").strip().lower() in {"1", "true", "yes", "on"}

    @classmethod
    def from_args(cls, args: Any, *, user: User | None) -> ItemFilters:
        return cls(
            query=(args.get("q") or "").strip() or None,
            category=args.get("category") or None,
            tag=args.get("tag") or None,
            difficulty=args.get("difficulty") or None,
            status=args.get("status") if user is not None else None,
            mine=cls._flag(args.get("mine")) and user is not None,
            featured=True if cls._flag(args.get("featured")) else None,
            sort=args.get("sort") if args.get("sort") in SORT_OPTIONS else "updated",
        )

    def as_query_args(self) -> dict[str, Any]:
        args: dict[str, Any] = {}
        if self.query:
            args["q"] = self.query
        for key in ("category", "tag", "difficulty", "status"):
            value = getattr(self, key)
            if value:
                args[key] = value
        if self.mine:
            args["mine"] = 1
        if self.featured:
            args["featured"] = 1
        if self.sort != "updated":
            args["sort"] = self.sort
        return args


def can_edit(item: KnowledgeItem, user: User | None) -> bool:
    if user is None or not getattr(user, "is_authenticated", False):
        return False
    return bool(user.is_admin or item.author_id == user.id or user.has_permission("items:edit_any"))


def build_listing(filters: ItemFilters, *, user: User | None) -> Select[KnowledgeItem]:
    stmt = KnowledgeItem.visible_to(user).options(
        selectinload(KnowledgeItem.author),
        selectinload(KnowledgeItem.category),
        selectinload(KnowledgeItem.tags),
    )
    if filters.mine and user is not None:
        stmt = stmt.where(KnowledgeItem.author_id == user.id)
    if filters.query:
        pattern = f"%{filters.query}%"
        stmt = stmt.where(
            KnowledgeItem.title.ilike(pattern)
            | KnowledgeItem.summary.ilike(pattern)
            | KnowledgeItem.content.ilike(pattern)
        )
    if filters.category:
        stmt = stmt.join(KnowledgeItem.category).where(Category.slug == filters.category)
    if filters.tag:
        stmt = stmt.where(KnowledgeItem.tags.any(Tag.slug == filters.tag))
    if filters.difficulty in {d.value for d in Difficulty}:
        stmt = stmt.where(KnowledgeItem.difficulty == Difficulty(filters.difficulty))
    if filters.status in {s.value for s in ItemStatus}:
        stmt = stmt.where(KnowledgeItem.status == ItemStatus(filters.status))
    if filters.featured:
        stmt = stmt.where(KnowledgeItem.is_featured.is_(True))
    return stmt.order_by(SORT_OPTIONS[filters.sort], KnowledgeItem.id.desc())


def get_by_slug(slug: str, *, user: User | None) -> KnowledgeItem | None:
    """Return the item when it exists *and* is visible to ``user``; else ``None``."""
    item = db.session.scalar(select(KnowledgeItem).where(KnowledgeItem.slug == slug))
    if item is None or not item.is_visible_to(user):
        return None
    return item


def _apply_fields(item: KnowledgeItem, data: dict[str, Any], *, actor: User) -> None:
    """Apply a (possibly partial) field mapping; absent keys are left untouched."""
    if "title" in data:
        item.title = sanitize_text(data["title"], max_length=200)
    if "summary" in data:
        item.summary = sanitize_text(data.get("summary"), max_length=500) or None
    if "content" in data:
        item.content = sanitize_html(data["content"])
    if "source_url" in data:
        item.source_url = (data.get("source_url") or "").strip() or None
    if data.get("difficulty"):
        item.difficulty = Difficulty(data["difficulty"])
    if data.get("status"):
        item.status = ItemStatus(data["status"])
    if "is_public" in data:
        item.is_public = bool(data["is_public"])
    if "is_featured" in data and actor.is_admin:
        item.is_featured = bool(data["is_featured"])
    if "category_id" in data:
        category_id = data["category_id"] or None
        item.category = db.session.get(Category, int(category_id)) if category_id else None
    if "tags" in data:
        item.set_tags(data["tags"])


def create_item(data: dict[str, Any], *, author: User) -> KnowledgeItem:
    item = KnowledgeItem(title=data["title"], content=data["content"], author=author)
    _apply_fields(item, data, actor=author)
    db.session.add(item)
    db.session.flush()
    record_activity("item.created", user=author, resource=item, title=item.title)
    db.session.commit()
    events.item_created(item)
    return item


def update_item(
    item: KnowledgeItem, data: dict[str, Any], *, actor: User, note: str | None = None
) -> KnowledgeItem:
    if not can_edit(item, actor):
        raise PermissionDeniedError
    item.bump_version(actor, note=note)
    _apply_fields(item, data, actor=actor)
    record_activity("item.updated", user=actor, resource=item, version=item.version)
    db.session.commit()
    events.item_updated(item, actor=actor.username)
    if item.author_id != actor.id and item.author.preference("email_notifications", True):
        notify(
            item.author,
            f"{actor.username} edited “{item.title}”",
            kind=NotificationKind.INFO,
            link=f"/knowledge/{item.slug}",
            commit=True,
        )
    return item


def delete_item(item: KnowledgeItem, *, actor: User) -> None:
    if not can_edit(item, actor):
        raise PermissionDeniedError
    slug, title = item.slug, item.title
    record_activity("item.deleted", user=actor, title=title, slug=slug)
    db.session.delete(item)
    db.session.commit()
    events.item_deleted(slug, title)


def restore_revision(
    item: KnowledgeItem, revision: KnowledgeItemRevision, *, actor: User
) -> KnowledgeItem:
    if not can_edit(item, actor) or revision.item_id != item.id:
        raise PermissionDeniedError
    item.bump_version(actor, note=f"Restored version {revision.version}")
    item.title = revision.title
    item.summary = revision.summary
    item.content = revision.content
    record_activity("item.restored", user=actor, resource=item, restored_version=revision.version)
    db.session.commit()
    return item


def record_view(item: KnowledgeItem) -> None:
    item.record_view()
    db.session.commit()


def toggle_bookmark(item: KnowledgeItem, *, user: User) -> bool:
    """Return ``True`` when the item is bookmarked after the call."""
    existing = db.session.scalar(
        select(Bookmark).where(Bookmark.user_id == user.id, Bookmark.item_id == item.id)
    )
    if existing is not None:
        db.session.delete(existing)
        db.session.commit()
        return False
    db.session.add(Bookmark(user=user, item=item))
    record_activity("item.bookmarked", user=user, resource=item)
    db.session.commit()
    return True


def is_bookmarked(item: KnowledgeItem, user: User | None) -> bool:
    if user is None or not getattr(user, "is_authenticated", False):
        return False
    return (
        db.session.scalar(
            select(Bookmark.id).where(Bookmark.user_id == user.id, Bookmark.item_id == item.id)
        )
        is not None
    )


def add_comment(
    item: KnowledgeItem, body: str, *, author: User, parent_id: int | None = None
) -> Comment:
    parent = db.session.get(Comment, parent_id) if parent_id else None
    if parent is not None and parent.item_id != item.id:
        parent = None
    comment = Comment(
        body=sanitize_text(body, max_length=5000), item=item, author=author, parent=parent
    )
    db.session.add(comment)
    db.session.flush()
    record_activity("comment.created", user=author, resource=comment, item_id=item.id)
    db.session.commit()
    events.comment_added(comment)
    recipients = {item.author} | ({parent.author} if parent is not None else set())
    for recipient in recipients - {author}:
        notify(
            recipient,
            f"{author.username} commented on “{item.title}”",
            body=comment.body[:140],
            kind=NotificationKind.MENTION,
            link=f"/knowledge/{item.slug}#comment-{comment.id}",
            commit=True,
        )
    return comment


def delete_comment(comment: Comment, *, actor: User) -> None:
    if not (actor.is_admin or actor.id in {comment.author_id, comment.item.author_id}):
        raise PermissionDeniedError
    comment.is_deleted = True
    record_activity("comment.deleted", user=actor, resource=comment, commit=True)


def bulk_action(action: str, item_ids: list[int], *, actor: User) -> int:
    """Apply ``action`` to every editable item in ``item_ids``; return the count affected."""
    items = db.session.scalars(select(KnowledgeItem).where(KnowledgeItem.id.in_(item_ids))).all()
    affected = 0
    for item in items:
        if not can_edit(item, actor):
            continue
        if action == "delete":
            db.session.delete(item)
        elif action == "publish":
            item.publish()
        elif action == "archive":
            item.archive()
        elif action == "make_public":
            item.is_public = True
        elif action == "make_private":
            item.is_public = False
        elif action in {"feature", "unfeature"}:
            if not actor.is_admin:
                continue
            item.is_featured = action == "feature"
        else:
            msg = f"unknown bulk action {action!r}"
            raise ValueError(msg)
        affected += 1
    if affected:
        record_activity("item.bulk_action", user=actor, action_name=action, count=affected)
    db.session.commit()
    return affected


def export_item(item: KnowledgeItem, fmt: str = "json") -> tuple[str, str]:
    """Serialise an item as ``(body, mimetype)`` in JSON or Markdown."""
    if fmt == "md":
        from app.utils.text import strip_html

        lines = [
            f"# {item.title}",
            "",
            f"*By {item.author.username} · v{item.version} · {item.updated_at:%Y-%m-%d}*",
            "",
        ]
        if item.summary:
            lines += [f"> {item.summary}", ""]
        lines += [strip_html(item.content), ""]
        if item.tag_names:
            lines.append("Tags: " + ", ".join(f"`{t}`" for t in item.tag_names))
        return "\n".join(lines), "text/markdown"
    import json

    return json.dumps(item.to_dict(), indent=2, ensure_ascii=False), "application/json"


__all__ = [
    "SORT_OPTIONS",
    "ItemFilters",
    "PermissionDeniedError",
    "add_comment",
    "build_listing",
    "bulk_action",
    "can_edit",
    "create_item",
    "delete_comment",
    "delete_item",
    "export_item",
    "get_by_slug",
    "is_bookmarked",
    "record_view",
    "restore_revision",
    "toggle_bookmark",
    "update_item",
]

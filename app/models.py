"""Domain model for FlaskVerseHub.

Design notes
------------
* SQLAlchemy 2.0 declarative style with ``Mapped`` annotations so the model is
  fully typed and checkable with mypy.
* Every timestamp is stored as UTC and read back timezone-aware through
  :class:`UTCDateTime`, regardless of the backend (SQLite drops tzinfo).
* :class:`KnowledgeItem` is the central aggregate: it owns tags, revisions,
  comments, attachments and bookmarks. Revisions give an append-only history
  so edits are reproducible and auditable.
* Visibility is a *policy*, expressed once in :meth:`KnowledgeItem.visible_to`,
  and reused by the vault, REST and GraphQL layers.
"""

from __future__ import annotations

import enum
import hashlib
import secrets
from datetime import datetime
from typing import Any

from flask_login import UserMixin
from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Table,
    Text,
    UniqueConstraint,
    event,
    select,
)
from sqlalchemy.engine import Dialect
from sqlalchemy.orm import Mapped, Mapper, Session, mapped_column, relationship, validates
from sqlalchemy.sql import Select
from sqlalchemy.types import TypeDecorator
from werkzeug.security import check_password_hash, generate_password_hash

from app.extensions import db
from app.utils.text import (
    parse_tag_list,
    reading_time_minutes,
    slugify,
    unique_slug,
    word_count,
)
from app.utils.time import ensure_aware, from_now, is_expired, utcnow

# --------------------------------------------------------------------------- #
# Column types and mixins
# --------------------------------------------------------------------------- #


class UTCDateTime(TypeDecorator[datetime]):
    """Store aware datetimes as naive UTC and return them aware.

    SQLite has no timezone support and PostgreSQL ``timestamp`` columns
    normalise to the session timezone; this decorator makes behaviour
    identical across both so comparisons never raise ``TypeError``.
    """

    impl = DateTime
    cache_ok = True

    def process_bind_param(self, value: datetime | None, _dialect: Dialect) -> datetime | None:
        aware = ensure_aware(value)
        return aware.replace(tzinfo=None) if aware is not None else None

    def process_result_value(self, value: datetime | None, _dialect: Dialect) -> datetime | None:
        return ensure_aware(value)


class TimestampMixin:
    """``created_at`` / ``updated_at`` maintained by the database layer."""

    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime, default=utcnow, onupdate=utcnow, nullable=False
    )


# --------------------------------------------------------------------------- #
# Association tables
# --------------------------------------------------------------------------- #

user_roles = Table(
    "user_roles",
    db.metadata,
    Column("user_id", Integer, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
    Column("role_id", Integer, ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True),
)

knowledge_item_tags = Table(
    "knowledge_item_tags",
    db.metadata,
    Column(
        "item_id", Integer, ForeignKey("knowledge_items.id", ondelete="CASCADE"), primary_key=True
    ),
    Column("tag_id", Integer, ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True),
)


# --------------------------------------------------------------------------- #
# Enumerations
# --------------------------------------------------------------------------- #


class ItemStatus(enum.StrEnum):
    DRAFT = "draft"
    PUBLISHED = "published"
    ARCHIVED = "archived"


class Difficulty(enum.StrEnum):
    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"
    EXPERT = "expert"


class NotificationKind(enum.StrEnum):
    INFO = "info"
    SUCCESS = "success"
    WARNING = "warning"
    MENTION = "mention"
    SYSTEM = "system"


# --------------------------------------------------------------------------- #
# Identity and access
# --------------------------------------------------------------------------- #


class Role(TimestampMixin, db.Model):
    __tablename__ = "roles"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(String(255))
    permissions: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    users: Mapped[list[User]] = relationship(
        "User", secondary=user_roles, back_populates="roles", lazy="selectin"
    )

    def __repr__(self) -> str:
        return f"<Role {self.name}>"


class User(UserMixin, TimestampMixin, db.Model):
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint("length(username) >= 3", name="ck_users_username_min_length"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)

    first_name: Mapped[str | None] = mapped_column(String(64))
    last_name: Mapped[str | None] = mapped_column(String(64))
    bio: Mapped[str | None] = mapped_column(Text)
    avatar_url: Mapped[str | None] = mapped_column(String(512))
    website: Mapped[str | None] = mapped_column(String(255))
    location: Mapped[str | None] = mapped_column(String(128))

    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    email_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    last_login: Mapped[datetime | None] = mapped_column(UTCDateTime)
    login_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    failed_login_attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    locked_until: Mapped[datetime | None] = mapped_column(UTCDateTime)

    timezone: Mapped[str] = mapped_column(String(64), default="UTC", nullable=False)
    language: Mapped[str] = mapped_column(String(8), default="en", nullable=False)
    theme: Mapped[str] = mapped_column(String(16), default="light", nullable=False)
    preferences: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)

    roles: Mapped[list[Role]] = relationship(
        "Role", secondary=user_roles, back_populates="users", lazy="selectin"
    )
    knowledge_items: Mapped[list[KnowledgeItem]] = relationship(
        "KnowledgeItem",
        back_populates="author",
        foreign_keys="KnowledgeItem.author_id",
        cascade="all, delete-orphan",
        lazy="dynamic",
    )
    api_keys: Mapped[list[ApiKey]] = relationship(
        "ApiKey", back_populates="owner", cascade="all, delete-orphan", lazy="dynamic"
    )
    activities: Mapped[list[Activity]] = relationship(
        "Activity", back_populates="user", cascade="all, delete-orphan", lazy="dynamic"
    )
    comments: Mapped[list[Comment]] = relationship(
        "Comment", back_populates="author", cascade="all, delete-orphan", lazy="dynamic"
    )
    bookmarks: Mapped[list[Bookmark]] = relationship(
        "Bookmark", back_populates="user", cascade="all, delete-orphan", lazy="dynamic"
    )
    notifications: Mapped[list[Notification]] = relationship(
        "Notification", back_populates="user", cascade="all, delete-orphan", lazy="dynamic"
    )

    MAX_FAILED_LOGINS = 5
    LOCKOUT_MINUTES = 15

    # -- credentials -------------------------------------------------------
    def set_password(self, password: str) -> None:
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)

    def register_failed_login(self) -> None:
        """Increment the failure counter and lock the account after repeated failures."""
        self.failed_login_attempts += 1
        if self.failed_login_attempts >= self.MAX_FAILED_LOGINS:
            self.locked_until = from_now(minutes=self.LOCKOUT_MINUTES)

    def register_successful_login(self) -> None:
        self.failed_login_attempts = 0
        self.locked_until = None
        self.login_count += 1
        self.last_login = utcnow()

    # -- derived state -----------------------------------------------------
    @property
    def is_locked(self) -> bool:
        return self.locked_until is not None and not is_expired(self.locked_until)

    @property
    def full_name(self) -> str:
        parts = [p for p in (self.first_name, self.last_name) if p]
        return " ".join(parts) if parts else self.username

    @property
    def role_names(self) -> set[str]:
        names = {role.name for role in self.roles}
        if self.is_admin:
            names.add("admin")
        return names

    def has_role(self, *names: str) -> bool:
        return self.is_admin or bool(self.role_names.intersection(names))

    def has_permission(self, permission: str) -> bool:
        if self.is_admin:
            return True
        return any(permission in role.permissions for role in self.roles)

    def preference(self, key: str, default: Any = None) -> Any:
        return (self.preferences or {}).get(key, default)

    def to_dict(self, *, include_email: bool = False) -> dict[str, Any]:
        data: dict[str, Any] = {
            "id": self.id,
            "username": self.username,
            "full_name": self.full_name,
            "first_name": self.first_name,
            "last_name": self.last_name,
            "bio": self.bio,
            "avatar_url": self.avatar_url,
            "is_admin": self.is_admin,
            "roles": sorted(self.role_names),
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "last_login": self.last_login.isoformat() if self.last_login else None,
        }
        if include_email:
            data["email"] = self.email
            data["email_verified"] = self.email_verified
        return data

    def __repr__(self) -> str:
        return f"<User {self.username}>"


class ApiKey(TimestampMixin, db.Model):
    """Hashed API credential. The clear-text key is shown exactly once at creation."""

    __tablename__ = "api_keys"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    prefix: Mapped[str] = mapped_column(String(12), nullable=False, index=True)
    key_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    scopes: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    expires_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    last_used_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    usage_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    owner: Mapped[User] = relationship("User", back_populates="api_keys")

    @staticmethod
    def hash_key(raw: str) -> str:
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    @classmethod
    def issue(
        cls, owner: User, name: str, *, scopes: list[str] | None = None
    ) -> tuple[ApiKey, str]:
        """Create a key for ``owner`` and return ``(record, clear_text_key)``."""
        raw = f"fvh_{secrets.token_urlsafe(32)}"
        record = cls(
            name=name,
            prefix=raw[:12],
            key_hash=cls.hash_key(raw),
            scopes=scopes or ["read"],
            owner=owner,
        )
        return record, raw

    @classmethod
    def lookup(cls, raw: str) -> ApiKey | None:
        record = db.session.scalar(select(cls).where(cls.key_hash == cls.hash_key(raw)))
        if record is None or not record.is_usable:
            return None
        return record

    @property
    def is_expired(self) -> bool:
        return is_expired(self.expires_at)

    @property
    def is_usable(self) -> bool:
        return self.is_active and not self.is_expired

    def touch(self) -> None:
        self.usage_count += 1
        self.last_used_at = utcnow()

    def __repr__(self) -> str:
        return f"<ApiKey {self.prefix}… ({self.name})>"


# --------------------------------------------------------------------------- #
# Knowledge domain
# --------------------------------------------------------------------------- #


class Category(TimestampMixin, db.Model):
    __tablename__ = "categories"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    slug: Mapped[str] = mapped_column(String(120), unique=True, nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text)
    color: Mapped[str] = mapped_column(String(7), default="#6c757d", nullable=False)
    icon: Mapped[str] = mapped_column(String(50), default="folder", nullable=False)
    parent_id: Mapped[int | None] = mapped_column(ForeignKey("categories.id", ondelete="SET NULL"))

    parent: Mapped[Category | None] = relationship(
        "Category", remote_side="Category.id", back_populates="children"
    )
    children: Mapped[list[Category]] = relationship("Category", back_populates="parent")
    items: Mapped[list[KnowledgeItem]] = relationship(
        "KnowledgeItem", back_populates="category", lazy="dynamic"
    )

    @property
    def item_count(self) -> int:
        return self.items.count()  # type: ignore[attr-defined]

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "slug": self.slug,
            "description": self.description,
            "color": self.color,
            "icon": self.icon,
            "parent_id": self.parent_id,
        }

    def __repr__(self) -> str:
        return f"<Category {self.slug}>"


class Tag(db.Model):
    __tablename__ = "tags"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    slug: Mapped[str] = mapped_column(String(60), unique=True, nullable=False, index=True)

    items: Mapped[list[KnowledgeItem]] = relationship(
        "KnowledgeItem", secondary=knowledge_item_tags, back_populates="tags", lazy="dynamic"
    )

    @classmethod
    def get_or_create(cls, name: str) -> Tag:
        normalized = " ".join(name.strip().lower().split())
        with db.session.no_autoflush:
            existing = db.session.scalar(select(cls).where(cls.name == normalized))
        if existing is not None:
            return existing
        tag = cls(name=normalized, slug=slugify(normalized, max_length=60))
        db.session.add(tag)
        return tag

    @property
    def usage_count(self) -> int:
        return self.items.count()  # type: ignore[attr-defined]

    def __repr__(self) -> str:
        return f"<Tag {self.name}>"


class KnowledgeItem(TimestampMixin, db.Model):
    __tablename__ = "knowledge_items"
    __table_args__ = (
        Index("ix_knowledge_items_visibility", "is_public", "status"),
        Index("ix_knowledge_items_author_created", "author_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    slug: Mapped[str] = mapped_column(String(220), unique=True, nullable=False, index=True)
    summary: Mapped[str | None] = mapped_column(String(500))
    content: Mapped[str] = mapped_column(Text, nullable=False)
    source_url: Mapped[str | None] = mapped_column(String(512))

    status: Mapped[ItemStatus] = mapped_column(
        Enum(ItemStatus, values_callable=lambda e: [m.value for m in e], native_enum=False),
        default=ItemStatus.PUBLISHED,
        nullable=False,
    )
    difficulty: Mapped[Difficulty] = mapped_column(
        Enum(Difficulty, values_callable=lambda e: [m.value for m in e], native_enum=False),
        default=Difficulty.INTERMEDIATE,
        nullable=False,
    )
    is_public: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_featured: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    view_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    like_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    published_at: Mapped[datetime | None] = mapped_column(UTCDateTime)

    author_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    updated_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    category_id: Mapped[int | None] = mapped_column(
        ForeignKey("categories.id", ondelete="SET NULL"), index=True
    )

    author: Mapped[User] = relationship(
        "User", back_populates="knowledge_items", foreign_keys=[author_id]
    )
    updated_by: Mapped[User | None] = relationship("User", foreign_keys=[updated_by_id])
    category: Mapped[Category | None] = relationship("Category", back_populates="items")
    tags: Mapped[list[Tag]] = relationship(
        "Tag", secondary=knowledge_item_tags, back_populates="items", lazy="selectin"
    )
    revisions: Mapped[list[KnowledgeItemRevision]] = relationship(
        "KnowledgeItemRevision",
        back_populates="item",
        cascade="all, delete-orphan",
        order_by="KnowledgeItemRevision.version.desc()",
        lazy="dynamic",
    )
    comments: Mapped[list[Comment]] = relationship(
        "Comment",
        back_populates="item",
        cascade="all, delete-orphan",
        order_by="Comment.created_at",
        lazy="dynamic",
    )
    attachments: Mapped[list[Attachment]] = relationship(
        "Attachment", back_populates="item", cascade="all, delete-orphan", lazy="dynamic"
    )
    bookmarks: Mapped[list[Bookmark]] = relationship(
        "Bookmark", back_populates="item", cascade="all, delete-orphan", lazy="dynamic"
    )

    # -- validation --------------------------------------------------------
    @validates("title")
    def _validate_title(self, _key: str, value: str) -> str:
        cleaned = " ".join((value or "").split())
        if not cleaned:
            raise ValueError("title must not be empty")
        return cleaned

    # -- derived content statistics ----------------------------------------
    @property
    def word_count(self) -> int:
        return word_count(self.content)

    @property
    def reading_time(self) -> int:
        return reading_time_minutes(self.content)

    @property
    def tag_names(self) -> list[str]:
        return [tag.name for tag in self.tags]

    @property
    def is_published(self) -> bool:
        return self.status == ItemStatus.PUBLISHED

    @property
    def category_name(self) -> str | None:
        return self.category.name if self.category else None

    # -- behaviour ---------------------------------------------------------
    def set_tags(self, value: str | list[str] | None) -> None:
        """Replace the tag set from a comma-separated string or list."""
        self.tags = [Tag.get_or_create(name) for name in parse_tag_list(value)]

    def publish(self) -> None:
        self.status = ItemStatus.PUBLISHED
        self.published_at = self.published_at or utcnow()

    def archive(self) -> None:
        self.status = ItemStatus.ARCHIVED

    def record_view(self) -> None:
        self.view_count += 1

    def snapshot(self, editor: User | None, *, note: str | None = None) -> KnowledgeItemRevision:
        """Append the *current* state to the revision history before an edit."""
        revision = KnowledgeItemRevision(
            item=self,
            version=self.version,
            title=self.title,
            summary=self.summary,
            content=self.content,
            editor=editor,
            note=note,
        )
        db.session.add(revision)
        return revision

    def bump_version(self, editor: User | None = None, *, note: str | None = None) -> None:
        """Snapshot and increment the version counter; call before mutating content."""
        self.snapshot(editor, note=note)
        self.version += 1
        if editor is not None:
            self.updated_by = editor

    def is_visible_to(self, user: User | None) -> bool:
        """Mirror of :meth:`visible_to` for a single instance."""
        if self.is_public and self.is_published:
            return True
        if user is None or not getattr(user, "is_authenticated", False):
            return False
        return bool(user.is_admin or self.author_id == user.id)

    @classmethod
    def visible_to(cls, user: User | None) -> Select[tuple[KnowledgeItem]]:
        """Base query for every item ``user`` may read.

        Anonymous users see published public items; authenticated users also
        see their own items; admins see everything.
        """
        stmt = select(cls)
        if user is not None and getattr(user, "is_authenticated", False):
            if user.is_admin:
                return stmt
            return stmt.where(
                (cls.author_id == user.id)
                | ((cls.is_public.is_(True)) & (cls.status == ItemStatus.PUBLISHED))
            )
        return stmt.where(cls.is_public.is_(True), cls.status == ItemStatus.PUBLISHED)

    def to_dict(self, *, include_content: bool = True) -> dict[str, Any]:
        data: dict[str, Any] = {
            "id": self.id,
            "title": self.title,
            "slug": self.slug,
            "summary": self.summary,
            "source_url": self.source_url,
            "status": self.status.value,
            "difficulty": self.difficulty.value,
            "is_public": self.is_public,
            "is_featured": self.is_featured,
            "version": self.version,
            "view_count": self.view_count,
            "like_count": self.like_count,
            "word_count": self.word_count,
            "reading_time": self.reading_time,
            "tags": self.tag_names,
            "category": self.category.to_dict() if self.category else None,
            "author": {"id": self.author.id, "username": self.author.username},
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "published_at": self.published_at.isoformat() if self.published_at else None,
        }
        if include_content:
            data["content"] = self.content
        return data

    def __repr__(self) -> str:
        return f"<KnowledgeItem {self.slug}>"


class KnowledgeItemRevision(db.Model):
    """Immutable snapshot of a knowledge item at a given version."""

    __tablename__ = "knowledge_item_revisions"
    __table_args__ = (UniqueConstraint("item_id", "version", name="uq_revision_item_version"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    item_id: Mapped[int] = mapped_column(
        ForeignKey("knowledge_items.id", ondelete="CASCADE"), nullable=False, index=True
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    summary: Mapped[str | None] = mapped_column(String(500))
    content: Mapped[str] = mapped_column(Text, nullable=False)
    note: Mapped[str | None] = mapped_column(String(255))
    editor_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, nullable=False)

    item: Mapped[KnowledgeItem] = relationship("KnowledgeItem", back_populates="revisions")
    editor: Mapped[User | None] = relationship("User")

    def __repr__(self) -> str:
        return f"<Revision item={self.item_id} v{self.version}>"


class Comment(TimestampMixin, db.Model):
    __tablename__ = "comments"

    id: Mapped[int] = mapped_column(primary_key=True)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    item_id: Mapped[int] = mapped_column(
        ForeignKey("knowledge_items.id", ondelete="CASCADE"), nullable=False, index=True
    )
    author_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    parent_id: Mapped[int | None] = mapped_column(ForeignKey("comments.id", ondelete="CASCADE"))

    item: Mapped[KnowledgeItem] = relationship("KnowledgeItem", back_populates="comments")
    author: Mapped[User] = relationship("User", back_populates="comments")
    parent: Mapped[Comment | None] = relationship(
        "Comment", remote_side="Comment.id", back_populates="replies"
    )
    replies: Mapped[list[Comment]] = relationship("Comment", back_populates="parent")

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "body": "" if self.is_deleted else self.body,
            "is_deleted": self.is_deleted,
            "item_id": self.item_id,
            "parent_id": self.parent_id,
            "author": {"id": self.author.id, "username": self.author.username},
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    def __repr__(self) -> str:
        return f"<Comment {self.id} on item {self.item_id}>"


class Bookmark(db.Model):
    __tablename__ = "bookmarks"
    __table_args__ = (UniqueConstraint("user_id", "item_id", name="uq_bookmark_user_item"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    item_id: Mapped[int] = mapped_column(
        ForeignKey("knowledge_items.id", ondelete="CASCADE"), nullable=False, index=True
    )
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, nullable=False)

    user: Mapped[User] = relationship("User", back_populates="bookmarks")
    item: Mapped[KnowledgeItem] = relationship("KnowledgeItem", back_populates="bookmarks")


class Attachment(TimestampMixin, db.Model):
    __tablename__ = "attachments"

    id: Mapped[int] = mapped_column(primary_key=True)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    content_type: Mapped[str] = mapped_column(String(100), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    checksum_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    download_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    item_id: Mapped[int] = mapped_column(
        ForeignKey("knowledge_items.id", ondelete="CASCADE"), nullable=False, index=True
    )
    uploaded_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))

    item: Mapped[KnowledgeItem] = relationship("KnowledgeItem", back_populates="attachments")
    uploaded_by: Mapped[User | None] = relationship("User")

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "filename": self.original_filename,
            "content_type": self.content_type,
            "size_bytes": self.size_bytes,
            "checksum_sha256": self.checksum_sha256,
            "download_count": self.download_count,
        }


# --------------------------------------------------------------------------- #
# Operational records
# --------------------------------------------------------------------------- #


class Activity(db.Model):
    """Append-only audit trail of user and system actions."""

    __tablename__ = "activities"
    __table_args__ = (Index("ix_activities_user_created", "user_id", "created_at"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    action: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    resource_type: Mapped[str | None] = mapped_column(String(50))
    resource_id: Mapped[int | None] = mapped_column(Integer)
    description: Mapped[str | None] = mapped_column(String(500))
    ip_address: Mapped[str | None] = mapped_column(String(45))
    user_agent: Mapped[str | None] = mapped_column(String(255))
    endpoint: Mapped[str | None] = mapped_column(String(100))
    extra_data: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, nullable=False)

    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    user: Mapped[User | None] = relationship("User", back_populates="activities")

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "action": self.action,
            "resource_type": self.resource_type,
            "resource_id": self.resource_id,
            "description": self.description,
            "user": {"id": self.user.id, "username": self.user.username} if self.user else None,
            "extra_data": self.extra_data,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    def __repr__(self) -> str:
        return f"<Activity {self.action} by {self.user_id}>"


class Notification(db.Model):
    __tablename__ = "notifications"
    __table_args__ = (Index("ix_notifications_user_unread", "user_id", "is_read"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    body: Mapped[str | None] = mapped_column(Text)
    kind: Mapped[NotificationKind] = mapped_column(
        Enum(NotificationKind, values_callable=lambda e: [m.value for m in e], native_enum=False),
        default=NotificationKind.INFO,
        nullable=False,
    )
    link: Mapped[str | None] = mapped_column(String(512))
    is_read: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    read_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, nullable=False)

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user: Mapped[User] = relationship("User", back_populates="notifications")

    def mark_read(self) -> None:
        if not self.is_read:
            self.is_read = True
            self.read_at = utcnow()

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "body": self.body,
            "kind": self.kind.value,
            "link": self.link,
            "is_read": self.is_read,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class Setting(TimestampMixin, db.Model):
    """Typed key/value store for runtime-adjustable application settings."""

    __tablename__ = "settings"

    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    value: Mapped[str | None] = mapped_column(Text)
    value_type: Mapped[str] = mapped_column(String(10), default="str", nullable=False)
    description: Mapped[str | None] = mapped_column(String(255))
    is_public: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    _CASTS: dict[str, Any] = {
        "str": str,
        "int": int,
        "float": float,
        "bool": lambda v: str(v).lower() in {"1", "true", "yes", "on"},
    }

    def get_value(self) -> Any:
        if self.value is None:
            return None
        return self._CASTS.get(self.value_type, str)(self.value)

    def set_value(self, value: Any) -> None:
        self.value_type = type(value).__name__ if type(value).__name__ in self._CASTS else "str"
        self.value = str(value)

    @classmethod
    def get(cls, key: str, default: Any = None) -> Any:
        record = db.session.get(cls, key)
        return record.get_value() if record is not None else default


# --------------------------------------------------------------------------- #
# ORM event hooks
# --------------------------------------------------------------------------- #


def _slug_exists(model: type[Any], slug: str, exclude_id: int | None) -> bool:
    stmt = select(model.id).where(model.slug == slug)
    if exclude_id is not None:
        stmt = stmt.where(model.id != exclude_id)
    return db.session.scalar(stmt) is not None


@event.listens_for(KnowledgeItem, "before_insert")
def _item_before_insert(_mapper: Mapper[Any], connection: Any, target: KnowledgeItem) -> None:  # noqa: ARG001
    if not target.slug:
        base = slugify(target.title)
        target.slug = unique_slug(base, lambda s: _slug_exists(KnowledgeItem, s, None))
    # Column defaults are not applied yet inside before_insert, so ``None`` means
    # "will become the default", i.e. published.
    if target.status in (None, ItemStatus.PUBLISHED) and target.published_at is None:
        target.published_at = utcnow()


@event.listens_for(KnowledgeItem, "before_update")
def _item_before_update(_mapper: Mapper[Any], connection: Any, target: KnowledgeItem) -> None:  # noqa: ARG001
    if target.status == ItemStatus.PUBLISHED and target.published_at is None:
        target.published_at = utcnow()


@event.listens_for(Category, "before_insert")
def _category_before_insert(_mapper: Mapper[Any], connection: Any, target: Category) -> None:  # noqa: ARG001
    if not target.slug:
        base = slugify(target.name)
        target.slug = unique_slug(base, lambda s: _slug_exists(Category, s, None))


@event.listens_for(Session, "before_flush")
def _assign_default_role(session: Session, _ctx: Any, _instances: Any) -> None:
    """Attach the default role to newly created users, if one is configured."""
    new_users = [obj for obj in session.new if isinstance(obj, User) and not obj.roles]
    if not new_users:
        return
    default_role = session.scalar(select(Role).where(Role.is_default.is_(True)))
    if default_role is None:
        return
    for user in new_users:
        user.roles.append(default_role)


__all__ = [
    "Activity",
    "ApiKey",
    "Attachment",
    "Bookmark",
    "Category",
    "Comment",
    "Difficulty",
    "ItemStatus",
    "KnowledgeItem",
    "KnowledgeItemRevision",
    "Notification",
    "NotificationKind",
    "Role",
    "Setting",
    "Tag",
    "UTCDateTime",
    "User",
    "knowledge_item_tags",
    "user_roles",
]

"""In-app notifications with optional real-time fan-out."""

from __future__ import annotations

from collections.abc import Iterable

from app.extensions import db, socketio
from app.models import Notification, NotificationKind, User


def notify(
    user: User,
    title: str,
    *,
    body: str | None = None,
    kind: NotificationKind = NotificationKind.INFO,
    link: str | None = None,
    commit: bool = False,
) -> Notification:
    """Create a notification for ``user`` and push it over the user's socket room."""
    notification = Notification(user=user, title=title, body=body, kind=kind, link=link)
    db.session.add(notification)
    if commit:
        db.session.commit()
        socketio.emit("notification", notification.to_dict(), to=f"user:{user.id}")
    return notification


def notify_many(users: Iterable[User], title: str, **kwargs: object) -> list[Notification]:
    return [notify(user, title, **kwargs) for user in users]  # type: ignore[arg-type]


def unread_count(user: User) -> int:
    return int(user.notifications.filter(Notification.is_read.is_(False)).count())


__all__ = ["notify", "notify_many", "unread_count"]

"""Audit-trail recording."""

from __future__ import annotations

from typing import Any

from flask import has_request_context, request

from app.extensions import db
from app.models import Activity, User


def record_activity(
    action: str,
    *,
    user: User | None = None,
    resource: Any | None = None,
    description: str | None = None,
    commit: bool = False,
    **extra: Any,
) -> Activity:
    """Append an :class:`Activity` row describing ``action``.

    Request metadata (ip, user agent, endpoint) is captured automatically when
    called inside a request. The row joins the current transaction; pass
    ``commit=True`` to flush immediately.
    """
    activity = Activity(
        action=action,
        description=description,
        user=user if user is not None and getattr(user, "is_authenticated", True) else None,
        resource_type=type(resource).__name__ if resource is not None else None,
        resource_id=getattr(resource, "id", None) if resource is not None else None,
        extra_data=extra,
    )
    if has_request_context():
        activity.ip_address = request.remote_addr
        activity.user_agent = (request.user_agent.string or "")[:255] or None
        activity.endpoint = request.endpoint
    db.session.add(activity)
    if commit:
        db.session.commit()
    return activity


__all__ = ["record_activity"]

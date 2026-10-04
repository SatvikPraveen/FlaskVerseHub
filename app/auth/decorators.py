"""Authorization decorators for view functions.

They compose with Flask-Login's ``login_required`` and raise ``403`` (or
``401`` for anonymous users) through the shared error handlers, so API and
HTML clients receive the appropriate representation.
"""

from __future__ import annotations

from collections.abc import Callable
from functools import wraps
from typing import Any, TypeVar

from flask import abort
from flask_login import current_user

F = TypeVar("F", bound=Callable[..., Any])


def _require(predicate: Callable[[Any], bool], message: str) -> Callable[[F], F]:
    def decorator(func: F) -> F:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            if not current_user.is_authenticated:
                abort(401, description="Authentication required.")
            if not predicate(current_user):
                abort(403, description=message)
            return func(*args, **kwargs)

        return wrapper  # type: ignore[return-value]

    return decorator


def admin_required(func: F) -> F:
    """Allow administrators only."""
    return _require(lambda user: bool(user.is_admin), "Administrator access required.")(func)


def role_required(*roles: str) -> Callable[[F], F]:
    """Allow users holding any of ``roles`` (admins always pass)."""
    return _require(
        lambda user: user.has_role(*roles), f"One of these roles is required: {', '.join(roles)}."
    )


def permission_required(permission: str) -> Callable[[F], F]:
    """Allow users whose roles grant ``permission`` (admins always pass)."""
    return _require(
        lambda user: user.has_permission(permission), f"Permission '{permission}' is required."
    )


def verified_required(func: F) -> F:
    """Allow users with a verified email address."""
    return _require(lambda user: bool(user.email_verified), "Please verify your email first.")(func)


__all__ = ["admin_required", "permission_required", "role_required", "verified_required"]

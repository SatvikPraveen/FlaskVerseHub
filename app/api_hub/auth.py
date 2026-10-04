"""API authentication: JWT bearer tokens or hashed API keys.

``api_auth`` resolves the caller into ``g.api_user`` from either an
``Authorization: Bearer <jwt>`` header (Flask-JWT-Extended) or an
``X-API-Key`` header. With ``optional=True`` anonymous access is allowed and
``g.api_user`` is ``None``; otherwise a 401 problem document is returned.
"""

from __future__ import annotations

from collections.abc import Callable
from functools import wraps
from typing import Any, TypeVar

from flask import g, request
from flask_jwt_extended import verify_jwt_in_request
from flask_jwt_extended.exceptions import JWTExtendedException
from jwt import PyJWTError

from app.errors import APIError
from app.extensions import db, jwt
from app.models import ApiKey, User

F = TypeVar("F", bound=Callable[..., Any])


@jwt.user_identity_loader
def _identity(user: User | str | int) -> str:
    return str(user.id if isinstance(user, User) else user)


@jwt.user_lookup_loader
def _lookup(_header: dict[str, Any], payload: dict[str, Any]) -> User | None:
    user = db.session.get(User, int(payload["sub"]))
    return user if user is not None and user.is_active else None


def _from_api_key() -> User | None:
    raw = request.headers.get("X-API-Key")
    if not raw:
        return None
    record = ApiKey.lookup(raw)
    if record is None or not record.owner.is_active:
        raise APIError("Invalid or expired API key.", 401, code="invalid_api_key")
    record.touch()
    db.session.commit()
    g.api_key = record
    return record.owner


def _from_jwt(*, refresh: bool = False) -> User | None:
    if not request.headers.get("Authorization", "").startswith("Bearer "):
        return None
    try:
        verify_jwt_in_request(refresh=refresh)
    except (JWTExtendedException, PyJWTError) as exc:
        raise APIError(f"Invalid token: {exc}", 401, code="invalid_token") from exc
    from flask_jwt_extended import current_user as jwt_user

    user = jwt_user._get_current_object()
    if user is None:
        raise APIError("Token refers to an unknown or inactive user.", 401, code="invalid_token")
    return user


def resolve_api_user(*, refresh: bool = False) -> User | None:
    """Resolve the caller once per request and cache on ``g``."""
    if "api_user" in g:
        return g.api_user
    g.api_key = None
    user = _from_jwt(refresh=refresh) or _from_api_key()
    g.api_user = user
    return user


def api_auth(*, optional: bool = False, scope: str | None = None) -> Callable[[F], F]:
    """Require (or optionally resolve) an authenticated API caller.

    ``scope`` is enforced for API keys only; JWT callers act with the full
    permissions of their account.
    """

    def decorator(func: F) -> F:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            user = resolve_api_user()
            if user is None and not optional:
                raise APIError("Authentication required.", 401, code="unauthorized")
            key = g.get("api_key")
            if (
                user is not None
                and scope
                and key is not None
                and scope not in key.scopes
                and "admin" not in key.scopes
            ):
                raise APIError(
                    f"This API key lacks the '{scope}' scope.", 403, code="insufficient_scope"
                )
            return func(*args, **kwargs)

        return wrapper  # type: ignore[return-value]

    return decorator


def current_api_user() -> User | None:
    return g.get("api_user")


__all__ = ["api_auth", "current_api_user", "resolve_api_user"]

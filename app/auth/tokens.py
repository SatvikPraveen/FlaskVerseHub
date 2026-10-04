"""Signed, time-limited tokens for email verification and password reset."""

from __future__ import annotations

from typing import Any

from flask import current_app
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

RESET_SALT = "password-reset"
VERIFY_SALT = "email-verify"


def _serializer(salt: str) -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(current_app.config["SECRET_KEY"], salt=salt)


def generate_token(payload: dict[str, Any], *, salt: str) -> str:
    return _serializer(salt).dumps(payload)


def verify_token(token: str, *, salt: str, max_age_seconds: int) -> dict[str, Any] | None:
    """Return the payload or ``None`` when the token is invalid or expired."""
    try:
        data = _serializer(salt).loads(token, max_age=max_age_seconds)
    except (BadSignature, SignatureExpired):
        return None
    return data if isinstance(data, dict) else None


__all__ = ["RESET_SALT", "VERIFY_SALT", "generate_token", "verify_token"]

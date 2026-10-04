"""Authentication use-cases, independent of HTTP.

Routes translate forms/JSON into calls on this module and map results to
responses. Keeping the logic here makes it reusable from the REST API and
unit-testable without a client.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from flask import url_for
from sqlalchemy import select

from app.auth.tokens import RESET_SALT, VERIFY_SALT, generate_token, verify_token
from app.extensions import db
from app.models import ApiKey, User
from app.services.activity import record_activity
from app.utils.mail import send_email
from app.utils.time import utcnow

RESET_TOKEN_MAX_AGE = 60 * 60  # one hour
VERIFY_TOKEN_MAX_AGE = 60 * 60 * 24 * 3  # three days


class LoginFailure(Enum):
    INVALID_CREDENTIALS = "invalid_credentials"
    LOCKED = "locked"
    INACTIVE = "inactive"


@dataclass(frozen=True, slots=True)
class LoginResult:
    user: User | None
    failure: LoginFailure | None = None

    @property
    def ok(self) -> bool:
        return self.user is not None and self.failure is None


class DuplicateAccountError(ValueError):
    """Username or email already registered."""


def find_by_identifier(identifier: str) -> User | None:
    """Look a user up by username *or* email, case-insensitively."""
    value = identifier.strip().lower()
    return db.session.scalar(
        select(User).where(
            (db.func.lower(User.username) == value) | (db.func.lower(User.email) == value)
        )
    )


def register_user(
    username: str,
    email: str,
    password: str,
    *,
    first_name: str | None = None,
    last_name: str | None = None,
    send_verification: bool = True,
) -> User:
    username = username.strip()
    email = email.strip().lower()
    clash = db.session.scalar(
        select(User).where(
            (db.func.lower(User.username) == username.lower()) | (User.email == email)
        )
    )
    if clash is not None:
        field = "username" if clash.username.lower() == username.lower() else "email"
        raise DuplicateAccountError(field)
    user = User(username=username, email=email, first_name=first_name, last_name=last_name)
    user.set_password(password)
    db.session.add(user)
    db.session.flush()
    record_activity("user.registered", user=user, resource=user)
    db.session.commit()
    if send_verification:
        send_verification_email(user)
    return user


def authenticate(identifier: str, password: str) -> LoginResult:
    user = find_by_identifier(identifier)
    if user is None:
        return LoginResult(None, LoginFailure.INVALID_CREDENTIALS)
    if user.is_locked:
        record_activity("user.login_blocked", user=user, reason="locked", commit=True)
        return LoginResult(user, LoginFailure.LOCKED)
    if not user.check_password(password):
        user.register_failed_login()
        record_activity("user.login_failed", user=user, commit=True)
        return LoginResult(user, LoginFailure.INVALID_CREDENTIALS)
    if not user.is_active:
        return LoginResult(user, LoginFailure.INACTIVE)
    user.register_successful_login()
    record_activity("user.login", user=user, commit=True)
    return LoginResult(user)


def change_password(user: User, current_password: str, new_password: str) -> bool:
    if not user.check_password(current_password):
        return False
    user.set_password(new_password)
    record_activity("user.password_changed", user=user, commit=True)
    return True


def send_verification_email(user: User) -> None:
    token = generate_token({"uid": user.id, "email": user.email}, salt=VERIFY_SALT)
    send_email(
        "Verify your email address",
        user.email,
        "verify_email",
        user=user,
        verify_url=url_for("auth.verify_email", token=token, _external=True),
    )


def verify_email(token: str) -> User | None:
    data = verify_token(token, salt=VERIFY_SALT, max_age_seconds=VERIFY_TOKEN_MAX_AGE)
    if not data:
        return None
    user = db.session.get(User, int(data.get("uid", 0)))
    if user is None or user.email != data.get("email"):
        return None
    if not user.email_verified:
        user.email_verified = True
        record_activity("user.email_verified", user=user, commit=True)
    return user


def request_password_reset(identifier: str) -> bool:
    """Send a reset link if the account exists. Always behaves the same externally."""
    user = find_by_identifier(identifier)
    if user is None:
        return False
    token = generate_token({"uid": user.id, "pw": user.password_hash[-16:]}, salt=RESET_SALT)
    send_email(
        "Reset your password",
        user.email,
        "reset_password",
        user=user,
        reset_url=url_for("auth.reset_password", token=token, _external=True),
        expires_minutes=RESET_TOKEN_MAX_AGE // 60,
    )
    record_activity("user.password_reset_requested", user=user, commit=True)
    return True


def user_for_reset_token(token: str) -> User | None:
    data = verify_token(token, salt=RESET_SALT, max_age_seconds=RESET_TOKEN_MAX_AGE)
    if not data:
        return None
    user = db.session.get(User, int(data.get("uid", 0)))
    # Binding the token to the current hash makes it single-use.
    if user is None or user.password_hash[-16:] != data.get("pw"):
        return None
    return user


def reset_password(token: str, new_password: str) -> User | None:
    user = user_for_reset_token(token)
    if user is None:
        return None
    user.set_password(new_password)
    user.failed_login_attempts = 0
    user.locked_until = None
    record_activity("user.password_reset", user=user, commit=True)
    return user


def issue_api_key(user: User, name: str, scopes: list[str]) -> tuple[ApiKey, str]:
    record, raw = ApiKey.issue(user, name, scopes=scopes)
    record_activity("apikey.created", user=user, resource=record, name=name)
    db.session.commit()
    return record, raw


def revoke_api_key(user: User, key_id: int) -> bool:
    record = db.session.get(ApiKey, key_id)
    if record is None or record.user_id != user.id:
        return False
    record.is_active = False
    record.expires_at = utcnow()
    record_activity("apikey.revoked", user=user, resource=record, commit=True)
    return True


def delete_account(user: User, password: str) -> bool:
    if not user.check_password(password):
        return False
    record_activity("user.deleted", description=f"account {user.username} deleted")
    db.session.delete(user)
    db.session.commit()
    return True


__all__ = [
    "DuplicateAccountError",
    "LoginFailure",
    "LoginResult",
    "authenticate",
    "change_password",
    "delete_account",
    "find_by_identifier",
    "issue_api_key",
    "register_user",
    "request_password_reset",
    "reset_password",
    "revoke_api_key",
    "send_verification_email",
    "user_for_reset_token",
    "verify_email",
]

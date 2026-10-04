"""Authentication, account management and authorization helpers."""

from flask import Blueprint

bp = Blueprint("auth", __name__)

from app.auth import routes  # noqa: E402, F401
from app.auth.decorators import (  # noqa: E402
    admin_required,
    permission_required,
    role_required,
)

__all__ = ["admin_required", "bp", "permission_required", "role_required"]

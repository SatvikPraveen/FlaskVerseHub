"""Public pages: landing, about, site-wide search, health and status."""

from flask import Blueprint

bp = Blueprint("main", __name__)

from app.main import routes  # noqa: E402, F401

__all__ = ["bp"]

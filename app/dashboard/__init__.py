"""Dashboard: personal overview, notifications, analytics and real-time events."""

from flask import Blueprint

bp = Blueprint("dashboard", __name__)

from app.dashboard import routes, sockets  # noqa: E402, F401

__all__ = ["bp"]

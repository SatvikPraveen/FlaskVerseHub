"""Uniform error handling: JSON for API clients, HTML for browsers."""

from app.errors.handlers import APIError, register_error_handlers

__all__ = ["APIError", "register_error_handlers"]

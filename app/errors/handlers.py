"""Application-wide error handlers.

The same exception produces a JSON problem document for API clients
(``/api/*`` paths or ``Accept: application/json``) and a rendered page for
browsers. Every payload includes the request id for support correlation.
"""

from __future__ import annotations

from typing import Any

from flask import Flask, Response, g, jsonify, render_template, request
from werkzeug.exceptions import HTTPException

from app.observability import log


class APIError(Exception):
    """Raise from any layer to return a structured error with a chosen status."""

    def __init__(
        self,
        message: str,
        status_code: int = 400,
        *,
        code: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.code = code or _default_code(status_code)
        self.details = details or {}

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "error": self.code,
            "message": self.message,
            "status": self.status_code,
        }
        if self.details:
            payload["details"] = self.details
        return payload


_CODES = {
    400: "bad_request",
    401: "unauthorized",
    403: "forbidden",
    404: "not_found",
    405: "method_not_allowed",
    409: "conflict",
    413: "payload_too_large",
    415: "unsupported_media_type",
    422: "unprocessable_entity",
    429: "rate_limited",
    500: "internal_error",
    503: "service_unavailable",
}

_TITLES = {
    400: "Bad request",
    401: "Authentication required",
    403: "Access denied",
    404: "Page not found",
    405: "Method not allowed",
    413: "Upload too large",
    429: "Too many requests",
    500: "Something went wrong",
    503: "Service unavailable",
}


def _default_code(status: int) -> str:
    return _CODES.get(status, "error")


def wants_json() -> bool:
    """True when the client is an API consumer rather than a browser."""
    if request.path.startswith("/api/") or request.path == "/metrics":
        return True
    if request.is_json:
        return True
    best = request.accept_mimetypes.best_match(["application/json", "text/html"])
    return best == "application/json" and (
        request.accept_mimetypes["application/json"] > request.accept_mimetypes["text/html"]
    )


def _render(
    status: int, message: str, code: str, details: dict[str, Any] | None = None
) -> Response:
    request_id = getattr(g, "request_id", None)
    if wants_json():
        payload: dict[str, Any] = {"error": code, "message": message, "status": status}
        if details:
            payload["details"] = details
        if request_id:
            payload["request_id"] = request_id
        response = jsonify(payload)
        response.status_code = status
        return response
    body = render_template(
        "errors/error.html",
        status=status,
        title=_TITLES.get(status, "Error"),
        message=message,
        request_id=request_id,
    )
    return Response(body, status=status, mimetype="text/html")


def register_error_handlers(app: Flask) -> None:
    @app.errorhandler(APIError)
    def _handle_api_error(error: APIError) -> Response:
        return _render(error.status_code, error.message, error.code, error.details)

    @app.errorhandler(HTTPException)
    def _handle_http_error(error: HTTPException) -> Response:
        status = error.code or 500
        message = error.description or _TITLES.get(status, "Error")
        if status >= 500:
            log.error("http_error", status=status, description=message)
        return _render(status, str(message), _default_code(status))

    @app.errorhandler(Exception)
    def _handle_unexpected(error: Exception) -> Response:
        if app.config.get("PROPAGATE_EXCEPTIONS"):
            raise error
        log.exception("unhandled_exception")
        from app.extensions import db

        db.session.rollback()
        return _render(500, "An unexpected error occurred.", "internal_error")


__all__ = ["APIError", "register_error_handlers", "wants_json"]

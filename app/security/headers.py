"""Defensive HTTP response headers."""

from __future__ import annotations

from flask import Flask, Response


def register_security_headers(app: Flask) -> None:
    if not app.config.get("SECURITY_HEADERS_ENABLED", True):
        return
    csp = str(app.config.get("CONTENT_SECURITY_POLICY", ""))
    secure_cookies = bool(app.config.get("SESSION_COOKIE_SECURE"))

    @app.after_request
    def _apply_headers(response: Response) -> Response:
        headers = response.headers
        headers.setdefault("X-Content-Type-Options", "nosniff")
        headers.setdefault("X-Frame-Options", "DENY")
        headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
        if csp and response.mimetype == "text/html":
            headers.setdefault("Content-Security-Policy", csp)
        if secure_cookies:
            headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
        return response


__all__ = ["register_security_headers"]

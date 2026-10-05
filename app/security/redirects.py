"""Open-redirect protection.

Only same-origin targets are ever followed. Absolute URLs pointing at this host are
reduced to their path/query/fragment so the value handed to ``redirect`` is always a
local, root-relative path that browsers cannot interpret as another origin.
"""

from __future__ import annotations

from urllib.parse import urlsplit, urlunsplit

from flask import request


def safe_local_path(target: str | None) -> str | None:
    """Return a root-relative path for ``target`` if it stays on this site, else ``None``."""
    if not target:
        return None
    if "\\" in target or any(ord(ch) < 0x20 or ord(ch) == 0x7F for ch in target):
        return None
    parts = urlsplit(target)
    if parts.scheme or parts.netloc:
        own = urlsplit(request.host_url)
        if parts.scheme not in {"http", "https"} or parts.netloc != own.netloc:
            return None
    path = parts.path or "/"
    if not path.startswith("/") or path.startswith("//"):
        return None
    return urlunsplit(("", "", path, parts.query, parts.fragment))

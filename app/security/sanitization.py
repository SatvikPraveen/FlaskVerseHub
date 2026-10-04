"""User-content sanitisation built on ``nh3`` (ammonia bindings).

Knowledge items accept a restricted subset of HTML so authors can format
content while cross-site scripting vectors are stripped server-side.
"""

from __future__ import annotations

import nh3
from markupsafe import escape

ALLOWED_TAGS: frozenset[str] = frozenset(
    {
        "a", "abbr", "b", "blockquote", "br", "code", "dd", "del", "div", "dl", "dt", "em",
        "h1", "h2", "h3", "h4", "h5", "h6", "hr", "i", "img", "kbd", "li", "mark", "ol", "p",
        "pre", "s", "small", "span", "strong", "sub", "sup", "table", "tbody", "td", "th",
        "thead", "tr", "u", "ul",
    }
)  # fmt: skip

ALLOWED_ATTRIBUTES: dict[str, set[str]] = {
    "a": {"href", "title", "rel"},
    "img": {"src", "alt", "title", "width", "height"},
    "code": {"class"},
    "pre": {"class"},
    "span": {"class"},
    "div": {"class"},
    "td": {"colspan", "rowspan"},
    "th": {"colspan", "rowspan", "scope"},
}

ALLOWED_URL_SCHEMES: frozenset[str] = frozenset({"http", "https", "mailto"})


def sanitize_html(value: str | None) -> str:
    """Return ``value`` with disallowed tags, attributes and URL schemes removed."""
    if not value:
        return ""
    return nh3.clean(
        value,
        tags=set(ALLOWED_TAGS),
        attributes=ALLOWED_ATTRIBUTES,
        url_schemes=set(ALLOWED_URL_SCHEMES),
        link_rel="noopener noreferrer nofollow",
        strip_comments=True,
    )


def sanitize_text(value: str | None, *, max_length: int | None = None) -> str:
    """Escape *all* markup and collapse whitespace for plain-text fields."""
    if not value:
        return ""
    text = " ".join(str(escape(value)).split())
    return text[:max_length] if max_length else text


__all__ = ["ALLOWED_ATTRIBUTES", "ALLOWED_TAGS", "sanitize_html", "sanitize_text"]

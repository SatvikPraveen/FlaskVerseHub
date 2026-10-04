"""Text utilities: slugs, word statistics, and excerpting."""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Callable, Iterable

_WORD_RE = re.compile(r"[\w'-]+", re.UNICODE)
_NON_SLUG_RE = re.compile(r"[^a-z0-9]+")
_HTML_TAG_RE = re.compile(r"<[^>]+>")

WORDS_PER_MINUTE = 200
"""Average adult silent reading speed used for reading-time estimates."""


def slugify(value: str, *, max_length: int = 80) -> str:
    """Return a URL-safe ASCII slug for ``value``.

    Accents are stripped via NFKD normalisation, everything that is not a
    lowercase letter or digit becomes a single hyphen, and the result is
    truncated at a word boundary to ``max_length`` characters.
    """
    normalized = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    slug = _NON_SLUG_RE.sub("-", normalized.lower()).strip("-")
    if len(slug) > max_length:
        slug = slug[:max_length].rsplit("-", 1)[0] or slug[:max_length]
    return slug or "item"


def unique_slug(base: str, exists: Callable[[str], bool], *, max_attempts: int = 1000) -> str:
    """Return ``base`` or ``base-N`` such that ``exists(slug)`` is false.

    ``exists`` is any predicate (typically a database lookup).
    """
    candidate = base
    for suffix in range(2, max_attempts + 2):
        if not exists(candidate):
            return candidate
        candidate = f"{base}-{suffix}"
    msg = f"could not find a unique slug for {base!r} in {max_attempts} attempts"
    raise RuntimeError(msg)


def strip_html(value: str) -> str:
    """Remove HTML tags, collapsing whitespace."""
    return re.sub(r"\s+", " ", _HTML_TAG_RE.sub(" ", value)).strip()


def tokenize(value: str) -> list[str]:
    """Lower-case word tokens of ``value`` (apostrophes and hyphens kept)."""
    return [token.lower() for token in _WORD_RE.findall(value)]


def word_count(value: str | None) -> int:
    """Number of word tokens in ``value`` (HTML tags are ignored)."""
    if not value:
        return 0
    return len(_WORD_RE.findall(strip_html(value)))


def reading_time_minutes(value: str | None, *, wpm: int = WORDS_PER_MINUTE) -> int:
    """Estimated reading time in whole minutes, never less than one for non-empty text."""
    words = word_count(value)
    if words == 0:
        return 0
    return max(1, round(words / wpm))


def excerpt(value: str | None, *, length: int = 200, suffix: str = "…") -> str:
    """Plain-text excerpt of ``value`` cut at a word boundary."""
    if not value:
        return ""
    text = strip_html(value)
    if len(text) <= length:
        return text
    cut = text[:length].rsplit(" ", 1)[0]
    return f"{cut}{suffix}"


def parse_tag_list(value: str | Iterable[str] | None) -> list[str]:
    """Normalise a comma-separated string or iterable into unique, ordered tag names."""
    if value is None:
        return []
    raw = value.split(",") if isinstance(value, str) else list(value)
    seen: set[str] = set()
    tags: list[str] = []
    for item in raw:
        name = " ".join(item.strip().lower().split())
        if name and name not in seen:
            seen.add(name)
            tags.append(name)
    return tags

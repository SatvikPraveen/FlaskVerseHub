"""Timezone-aware time helpers.

All timestamps in FlaskVerseHub are UTC and timezone-aware. SQLite discards
timezone information, so :class:`app.models.UTCDateTime` re-attaches UTC on
load; these helpers give the rest of the codebase a single, correct way to
produce and compare instants.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta


def utcnow() -> datetime:
    """Return the current instant as an aware UTC datetime."""
    return datetime.now(UTC)


def ensure_aware(value: datetime | None) -> datetime | None:
    """Coerce a possibly-naive datetime to aware UTC (naive values are assumed UTC)."""
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def is_expired(deadline: datetime | None) -> bool:
    """True when ``deadline`` is in the past (``None`` never expires)."""
    aware = ensure_aware(deadline)
    return aware is not None and aware <= utcnow()


def from_now(**delta: float) -> datetime:
    """Return ``utcnow() + timedelta(**delta)``."""
    return utcnow() + timedelta(**delta)


def humanize_delta(value: datetime | None, *, now: datetime | None = None) -> str:
    """Render ``value`` relative to ``now`` ("3 hours ago", "just now", "in 2 days")."""
    aware = ensure_aware(value)
    if aware is None:
        return ""
    reference = ensure_aware(now) or utcnow()
    seconds = int((reference - aware).total_seconds())
    future = seconds < 0
    seconds = abs(seconds)
    units: list[tuple[str, int]] = [
        ("year", 365 * 86400),
        ("month", 30 * 86400),
        ("day", 86400),
        ("hour", 3600),
        ("minute", 60),
    ]
    for name, size in units:
        if seconds >= size:
            count = seconds // size
            label = f"{count} {name}{'s' if count != 1 else ''}"
            return f"in {label}" if future else f"{label} ago"
    return "just now"

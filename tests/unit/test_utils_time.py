from datetime import UTC, datetime, timedelta, timezone

import pytest
from freezegun import freeze_time

from app.utils.time import ensure_aware, from_now, humanize_delta, is_expired, utcnow

pytestmark = pytest.mark.unit


def test_utcnow_is_aware() -> None:
    assert utcnow().tzinfo is UTC


def test_ensure_aware_assumes_utc_for_naive() -> None:
    naive = datetime(2026, 1, 1, 12, 0)
    assert ensure_aware(naive) == datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
    assert ensure_aware(None) is None
    eastern = datetime(2026, 1, 1, 7, 0, tzinfo=timezone(timedelta(hours=-5)))
    assert ensure_aware(eastern) == datetime(2026, 1, 1, 12, 0, tzinfo=UTC)


@freeze_time("2026-06-01 12:00:00")
def test_is_expired_and_from_now() -> None:
    assert is_expired(None) is False
    assert is_expired(from_now(minutes=-1)) is True
    assert is_expired(from_now(minutes=1)) is False
    assert is_expired(datetime(2026, 6, 1, 11, 59)) is True  # naive, assumed UTC


@freeze_time("2026-06-01 12:00:00")
@pytest.mark.parametrize(
    ("delta", "expected"),
    [
        (timedelta(seconds=5), "just now"),
        (timedelta(minutes=1), "1 minute ago"),
        (timedelta(minutes=5), "5 minutes ago"),
        (timedelta(hours=3), "3 hours ago"),
        (timedelta(days=1), "1 day ago"),
        (timedelta(days=45), "1 month ago"),
        (timedelta(days=800), "2 years ago"),
        (timedelta(days=-2), "in 2 days"),
    ],
)
def test_humanize_delta(delta: timedelta, expected: str) -> None:
    assert humanize_delta(utcnow() - delta) == expected


def test_humanize_delta_none() -> None:
    assert humanize_delta(None) == ""

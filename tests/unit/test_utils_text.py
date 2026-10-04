import pytest
from hypothesis import given, strategies as st

from app.utils.text import (
    excerpt,
    parse_tag_list,
    reading_time_minutes,
    slugify,
    strip_html,
    tokenize,
    unique_slug,
    word_count,
)

pytestmark = pytest.mark.unit


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("Hello World", "hello-world"),
        ("  Trim   me  ", "trim-me"),
        ("Crème brûlée & café", "creme-brulee-cafe"),
        ("snake_case_title", "snake-case-title"),
        ("", "item"),
        ("!!!", "item"),
    ],
)
def test_slugify(raw: str, expected: str) -> None:
    assert slugify(raw) == expected


def test_slugify_truncates_on_word_boundary() -> None:
    slug = slugify("alpha beta gamma delta epsilon", max_length=12)
    assert slug == "alpha-beta"
    assert len(slug) <= 12


@given(st.text(min_size=1, max_size=200))
def test_slugify_is_url_safe_and_idempotent(value: str) -> None:
    slug = slugify(value)
    assert slug
    assert all(ch.isalnum() or ch == "-" for ch in slug)
    assert slugify(slug) == slug


def test_unique_slug_appends_counter() -> None:
    taken = {"post", "post-2"}
    assert unique_slug("post", taken.__contains__) == "post-3"
    assert unique_slug("fresh", taken.__contains__) == "fresh"


def test_unique_slug_gives_up() -> None:
    with pytest.raises(RuntimeError):
        unique_slug("x", lambda _: True, max_attempts=3)


def test_strip_html_and_tokenize() -> None:
    assert strip_html("<p>Hello <b>world</b></p>") == "Hello world"
    assert tokenize("Don't stop-believing, Flask!") == ["don't", "stop-believing", "flask"]


@pytest.mark.parametrize(
    ("text", "words", "minutes"),
    [
        ("", 0, 0),
        (None, 0, 0),
        ("one two three", 3, 1),
        ("w " * 450, 450, 2),
        ("<p>" + "w " * 199 + "</p>", 199, 1),
    ],
)
def test_word_count_and_reading_time(text: str | None, words: int, minutes: int) -> None:
    assert word_count(text) == words
    assert reading_time_minutes(text) == minutes


def test_excerpt_cuts_on_word_boundary() -> None:
    text = "The quick brown fox jumps over the lazy dog"
    assert excerpt(text, length=15) == "The quick brown…"
    assert excerpt(text, length=100) == text
    assert excerpt(None) == ""


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("Flask, python ,flask", ["flask", "python"]),
        (["A", "a", " B  C "], ["a", "b c"]),
        ("", []),
        (None, []),
    ],
)
def test_parse_tag_list(raw: str | list[str] | None, expected: list[str]) -> None:
    assert parse_tag_list(raw) == expected

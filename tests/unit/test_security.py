import pytest

from app.security.sanitization import sanitize_html, sanitize_text
from app.utils.diff import change_ratio, inline_diff

pytestmark = pytest.mark.unit


def test_sanitize_html_strips_scripts_and_event_handlers() -> None:
    dirty = '<p onclick="evil()">Hi <script>alert(1)</script><b>there</b></p>'
    assert sanitize_html(dirty) == "<p>Hi <b>there</b></p>"


def test_sanitize_html_links_get_safe_rel_and_schemes() -> None:
    cleaned = sanitize_html('<a href="javascript:alert(1)">x</a> <a href="https://e.com">ok</a>')
    assert "javascript:" not in cleaned
    assert 'rel="noopener noreferrer nofollow"' in cleaned
    assert 'href="https://e.com"' in cleaned


def test_sanitize_html_keeps_allowed_structure() -> None:
    html = '<h2>T</h2><pre><code class="language-python">x = 1</code></pre><img src="https://i/x.png" alt="a">'
    cleaned = sanitize_html(html)
    assert "<h2>" in cleaned and 'class="language-python"' in cleaned and "<img" in cleaned
    assert sanitize_html(None) == "" and sanitize_html("") == ""


def test_sanitize_text_escapes_and_truncates() -> None:
    assert sanitize_text("  <b>hi</b>   there ") == "&lt;b&gt;hi&lt;/b&gt; there"
    assert sanitize_text("abcdef", max_length=3) == "abc"
    assert sanitize_text(None) == ""


def test_inline_diff_marks_changes_and_escapes() -> None:
    result = str(inline_diff("the quick fox", "the slow <fox>"))
    assert "<del>quick</del>" in result
    assert "<ins>slow</ins>" in result
    assert "&lt;fox&gt;" in result and "<fox>" not in result
    assert str(inline_diff("same", "same")) == "same"


def test_change_ratio_bounds() -> None:
    assert change_ratio("a b c", "a b c") == 1.0
    assert change_ratio("a b c", "x y z") < 0.5
    assert 0.0 < change_ratio("a b c d", "a b x d") < 1.0


@pytest.mark.parametrize(
    ("target", "expected"),
    [
        ("/about", "/about"),
        ("/vault/?page=2#top", "/vault/?page=2#top"),
        ("http://localhost/vault/x?y=1", "/vault/x?y=1"),
        ("https://evil.example/x", None),
        ("//evil.example/x", None),
        ("/\\evil.example", None),
        ("\\\\evil.example", None),
        ("javascript:alert(1)", None),
        ("/ok\n", None),
        ("relative/path", None),
        ("", None),
        (None, None),
    ],
)
def test_safe_local_path(app, target, expected) -> None:  # type: ignore[no-untyped-def]
    from app.security.redirects import safe_local_path

    with app.test_request_context("/", base_url="http://localhost"):
        assert safe_local_path(target) == expected

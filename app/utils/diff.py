"""Word-level inline diffs for revision history."""

from __future__ import annotations

import re
from difflib import SequenceMatcher

from markupsafe import Markup, escape

_TOKEN_RE = re.compile(r"\s+|[^\s]+")


def _tokens(text: str) -> list[str]:
    return _TOKEN_RE.findall(text or "")


def inline_diff(old: str, new: str) -> Markup:
    """Return ``new`` with insertions in ``<ins>`` and deletions in ``<del>``.

    Both inputs are HTML-escaped first, so the result is safe to render.
    """
    a, b = _tokens(old), _tokens(new)
    matcher = SequenceMatcher(a=a, b=b, autojunk=False)
    parts: list[str] = []
    for op, i1, i2, j1, j2 in matcher.get_opcodes():
        if op == "equal":
            parts.append(str(escape("".join(a[i1:i2]))))
        if op in {"delete", "replace"}:
            parts.append(f"<del>{escape(''.join(a[i1:i2]))}</del>")
        if op in {"insert", "replace"}:
            parts.append(f"<ins>{escape(''.join(b[j1:j2]))}</ins>")
    return Markup("".join(parts))  # noqa: S704 - every fragment is escaped above


def change_ratio(old: str, new: str) -> float:
    """Similarity in ``[0, 1]`` (1.0 means identical)."""
    return SequenceMatcher(a=_tokens(old), b=_tokens(new), autojunk=False).ratio()


__all__ = ["change_ratio", "inline_diff"]

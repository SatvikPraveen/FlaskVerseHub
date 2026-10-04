"""Text analysis: tokenisation, stop words and stemming.

The :class:`Analyzer` is deliberately configurable so experiments can isolate
the effect of each normalisation step on retrieval effectiveness.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass, field

_TOKEN_RE = re.compile(r"[a-z0-9]+(?:['\u2019][a-z]+)?", re.IGNORECASE)
_HTML_RE = re.compile(r"<[^>]+>")

# A compact English stop list (Fox 1989 subset + web/programming filler).
DEFAULT_STOPWORDS: frozenset[str] = frozenset(
    [
        "a",
        "about",
        "above",
        "after",
        "again",
        "against",
        "all",
        "am",
        "an",
        "and",
        "any",
        "are",
        "aren't",
        "as",
        "at",
        "be",
        "because",
        "been",
        "before",
        "being",
        "below",
        "between",
        "both",
        "but",
        "by",
        "can",
        "cannot",
        "could",
        "couldn't",
        "did",
        "didn't",
        "do",
        "does",
        "doesn't",
        "doing",
        "don't",
        "down",
        "during",
        "each",
        "few",
        "for",
        "from",
        "further",
        "had",
        "hadn't",
        "has",
        "hasn't",
        "have",
        "haven't",
        "having",
        "he",
        "he'd",
        "he'll",
        "he's",
        "her",
        "here",
        "here's",
        "hers",
        "herself",
        "him",
        "himself",
        "his",
        "how",
        "how's",
        "i",
        "i'd",
        "i'll",
        "i'm",
        "i've",
        "if",
        "in",
        "into",
        "is",
        "isn't",
        "it",
        "it's",
        "its",
        "itself",
        "let's",
        "me",
        "more",
        "most",
        "mustn't",
        "my",
        "myself",
        "no",
        "nor",
        "not",
        "of",
        "off",
        "on",
        "once",
        "only",
        "or",
        "other",
        "ought",
        "our",
        "ours",
        "ourselves",
        "out",
        "over",
        "own",
        "same",
        "shan't",
        "she",
        "she'd",
        "she'll",
        "she's",
        "should",
        "shouldn't",
        "so",
        "some",
        "such",
        "than",
        "that",
        "that's",
        "the",
        "their",
        "theirs",
        "them",
        "themselves",
        "then",
        "there",
        "there's",
        "these",
        "they",
        "they'd",
        "they'll",
        "they're",
        "they've",
        "this",
        "those",
        "through",
        "to",
        "too",
        "under",
        "until",
        "up",
        "very",
        "was",
        "wasn't",
        "we",
        "we'd",
        "we'll",
        "we're",
        "we've",
        "were",
        "weren't",
        "what",
        "what's",
        "when",
        "when's",
        "where",
        "where's",
        "which",
        "while",
        "who",
        "who's",
        "whom",
        "why",
        "why's",
        "with",
        "won't",
        "would",
        "wouldn't",
        "you",
        "you'd",
        "you'll",
        "you're",
        "you've",
        "your",
        "yours",
        "yourself",
        "yourselves",
        "also",
        "use",
        "using",
        "used",
        "via",
        "etc",
        "e.g",
        "i.e",
    ]
)


# --------------------------------------------------------------------------- #
# Porter stemmer (Porter, 1980). Faithful to the original algorithm.
# --------------------------------------------------------------------------- #

_VOWELS = set("aeiou")


def _is_consonant(word: str, i: int) -> bool:
    ch = word[i]
    if ch in _VOWELS:
        return False
    if ch == "y":
        return i == 0 or not _is_consonant(word, i - 1)
    return True


def _measure(stem: str) -> int:
    """Number of VC sequences, m, in the Porter sense."""
    m = 0
    i = 0
    n = len(stem)
    while i < n and _is_consonant(stem, i):
        i += 1
    while i < n:
        while i < n and not _is_consonant(stem, i):
            i += 1
        if i >= n:
            break
        m += 1
        while i < n and _is_consonant(stem, i):
            i += 1
    return m


def _contains_vowel(stem: str) -> bool:
    return any(not _is_consonant(stem, i) for i in range(len(stem)))


def _ends_double_consonant(word: str) -> bool:
    return len(word) >= 2 and word[-1] == word[-2] and _is_consonant(word, len(word) - 1)


def _cvc(word: str) -> bool:
    """*o condition: ends cvc where the second c is not w, x or y."""
    if len(word) < 3:
        return False
    return (
        _is_consonant(word, len(word) - 3)
        and not _is_consonant(word, len(word) - 2)
        and _is_consonant(word, len(word) - 1)
        and word[-1] not in "wxy"
    )


def _replace(word: str, suffix: str, replacement: str, condition: int | None = None) -> str | None:
    if not word.endswith(suffix):
        return None
    stem = word[: len(word) - len(suffix)]
    if (
        condition is not None and _measure(stem) <= condition - 1 + 0
    ):  # m > condition-1  <=> m >= condition
        return None
    return stem + replacement


def porter_stem(word: str) -> str:  # noqa: PLR0912, PLR0915 - algorithmic by nature
    """Return the Porter stem of a lowercase ``word``."""
    if len(word) <= 2:
        return word
    w = word

    # Step 1a
    if w.endswith("sses") or w.endswith("ies"):
        w = w[:-2]
    elif w.endswith("ss"):
        pass
    elif w.endswith("s"):
        w = w[:-1]

    # Step 1b
    step1b_extra = False
    if w.endswith("eed"):
        if _measure(w[:-3]) > 0:
            w = w[:-1]
    elif w.endswith("ed") and _contains_vowel(w[:-2]):
        w = w[:-2]
        step1b_extra = True
    elif w.endswith("ing") and _contains_vowel(w[:-3]):
        w = w[:-3]
        step1b_extra = True
    if step1b_extra:
        if w.endswith(("at", "bl", "iz")):
            w += "e"
        elif _ends_double_consonant(w) and w[-1] not in "lsz":
            w = w[:-1]
        elif _measure(w) == 1 and _cvc(w):
            w += "e"

    # Step 1c
    if w.endswith("y") and _contains_vowel(w[:-1]):
        w = w[:-1] + "i"

    # Step 2
    step2 = (
        ("ational", "ate"), ("tional", "tion"), ("enci", "ence"), ("anci", "ance"), ("izer", "ize"),
        ("abli", "able"), ("alli", "al"), ("entli", "ent"), ("eli", "e"), ("ousli", "ous"),
        ("ization", "ize"), ("ation", "ate"), ("ator", "ate"), ("alism", "al"), ("iveness", "ive"),
        ("fulness", "ful"), ("ousness", "ous"), ("aliti", "al"), ("iviti", "ive"), ("biliti", "ble"),
    )  # fmt: skip
    for suffix, replacement in step2:
        if w.endswith(suffix):
            stem = w[: -len(suffix)]
            if _measure(stem) > 0:
                w = stem + replacement
            break

    # Step 3
    step3 = (
        ("icate", "ic"), ("ative", ""), ("alize", "al"), ("iciti", "ic"), ("ical", "ic"),
        ("ful", ""), ("ness", ""),
    )  # fmt: skip
    for suffix, replacement in step3:
        if w.endswith(suffix):
            stem = w[: -len(suffix)]
            if _measure(stem) > 0:
                w = stem + replacement
            break

    # Step 4
    step4 = (
        "al", "ance", "ence", "er", "ic", "able", "ible", "ant", "ement", "ment", "ent", "ion",
        "ou", "ism", "ate", "iti", "ous", "ive", "ize",
    )  # fmt: skip
    for suffix in step4:
        if w.endswith(suffix):
            stem = w[: -len(suffix)]
            if _measure(stem) > 1 and (suffix != "ion" or (stem and stem[-1] in "st")):
                w = stem
            break

    # Step 5a
    if w.endswith("e"):
        stem = w[:-1]
        m = _measure(stem)
        if m > 1 or (m == 1 and not _cvc(stem)):
            w = stem

    # Step 5b
    if _measure(w) > 1 and _ends_double_consonant(w) and w.endswith("l"):
        w = w[:-1]

    return w


# --------------------------------------------------------------------------- #
# Analyzer
# --------------------------------------------------------------------------- #


@dataclass(frozen=True, slots=True)
class Analyzer:
    """Turn raw text into a list of normalised terms.

    Parameters
    ----------
    lowercase:
        Case-fold tokens.
    stopwords:
        Terms to drop (after lower-casing). Pass an empty set to keep all.
    stem:
        Apply the Porter stemmer.
    min_length:
        Drop tokens shorter than this many characters.
    strip_html:
        Remove HTML tags before tokenising.
    """

    lowercase: bool = True
    stopwords: frozenset[str] = field(default=DEFAULT_STOPWORDS)
    stem: bool = True
    min_length: int = 2
    strip_html: bool = True

    def tokenize(self, text: str | None) -> list[str]:
        if not text:
            return []
        if self.strip_html:
            text = _HTML_RE.sub(" ", text)
        tokens = _TOKEN_RE.findall(text)
        if self.lowercase:
            tokens = [t.lower() for t in tokens]
        return [t.replace("\u2019", "'") for t in tokens]

    def analyze(self, text: str | None) -> list[str]:
        terms: list[str] = []
        for token in self.tokenize(text):
            if len(token) < self.min_length or token in self.stopwords:
                continue
            terms.append(porter_stem(token) if self.stem else token)
        return terms

    def analyze_many(self, texts: Iterable[str | None]) -> list[list[str]]:
        return [self.analyze(text) for text in texts]

    @property
    def name(self) -> str:
        parts = ["lower" if self.lowercase else "case"]
        parts.append("stop" if self.stopwords else "nostop")
        parts.append("porter" if self.stem else "nostem")
        return "+".join(parts)


__all__ = ["DEFAULT_STOPWORDS", "Analyzer", "porter_stem"]

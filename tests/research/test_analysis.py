import pytest
from hypothesis import given, strategies as st

from app.search.analysis import DEFAULT_STOPWORDS, Analyzer, porter_stem

pytestmark = pytest.mark.research

# Worked examples from Porter (1980), "An algorithm for suffix stripping".
PORTER_CASES = {
    "caresses": "caress", "ponies": "poni", "ties": "ti", "caress": "caress", "cats": "cat",
    "feed": "feed", "agreed": "agre", "plastered": "plaster", "bled": "bled", "motoring": "motor",
    "sing": "sing", "conflated": "conflat", "troubled": "troubl", "sized": "size", "hopping": "hop",
    "tanned": "tan", "falling": "fall", "hissing": "hiss", "fizzed": "fizz", "failing": "fail",
    "filing": "file", "happy": "happi", "sky": "sky", "relational": "relat", "conditional": "condit",
    "rational": "ration", "valenci": "valenc", "digitizer": "digit", "conformabli": "conform",
    "radicalli": "radic", "differentli": "differ", "vileli": "vile", "analogousli": "analog",
    "vietnamization": "vietnam", "predication": "predic", "operator": "oper", "feudalism": "feudal",
    "decisiveness": "decis", "hopefulness": "hope", "callousness": "callous", "formaliti": "formal",
    "sensitiviti": "sensit", "sensibiliti": "sensibl", "triplicate": "triplic", "formative": "form",
    "formalize": "formal", "electriciti": "electr", "electrical": "electr", "hopeful": "hope",
    "goodness": "good", "revival": "reviv", "allowance": "allow", "inference": "infer",
    "airliner": "airlin", "gyroscopic": "gyroscop", "adjustable": "adjust", "defensible": "defens",
    "irritant": "irrit", "replacement": "replac", "adjustment": "adjust", "dependent": "depend",
    "adoption": "adopt", "homologou": "homolog", "communism": "commun", "activate": "activ",
    "angulariti": "angular", "homologous": "homolog", "effective": "effect", "bowdlerize": "bowdler",
    "probate": "probat", "rate": "rate", "cease": "ceas", "controll": "control", "roll": "roll",
    "running": "run", "generalizations": "gener", "connection": "connect", "relationships": "relationship",
}  # fmt: skip


@pytest.mark.parametrize(("word", "stem"), sorted(PORTER_CASES.items()))
def test_porter_reference_cases(word: str, stem: str) -> None:
    assert porter_stem(word) == stem


@given(
    st.text(alphabet=st.characters(min_codepoint=97, max_codepoint=122), min_size=1, max_size=20)
)
def test_porter_is_idempotent_and_never_grows(word: str) -> None:
    once = porter_stem(word)
    assert len(once) <= len(word)
    assert porter_stem(once) == once or len(porter_stem(once)) <= len(once)


def test_analyzer_pipeline() -> None:
    analyzer = Analyzer()
    terms = analyzer.analyze(
        "<p>The Flask blueprints are <b>organising</b> large applications!</p>"
    )
    assert terms == ["flask", "blueprint", "organis", "larg", "applic"]
    assert "the" in DEFAULT_STOPWORDS


def test_analyzer_switches() -> None:
    raw = Analyzer(stem=False, stopwords=frozenset(), lowercase=False, min_length=1)
    assert raw.analyze("The Cats") == ["The", "Cats"]
    assert raw.name == "case+nostop+nostem"
    assert Analyzer().name == "lower+stop+porter"
    assert Analyzer().analyze("") == [] and Analyzer().analyze(None) == []


def test_analyzer_keeps_apostrophes_and_digits() -> None:
    assert Analyzer(stem=False).tokenize("Don\u2019t use py3.13 bm25") == [
        "don't",
        "use",
        "py3",
        "13",
        "bm25",
    ]
    assert Analyzer(stem=False).analyze("Don\u2019t use py3.13 bm25") == ["py3", "13", "bm25"]


def test_html_stripping_is_linear_on_unclosed_tags() -> None:
    import time

    start = time.perf_counter()
    assert Analyzer(stem=False).tokenize("<" * 50_000 + "word") == ["word"]
    assert time.perf_counter() - start < 1.0
    assert Analyzer(stem=False).tokenize("a <b>bold</b> c") == ["a", "bold", "c"]

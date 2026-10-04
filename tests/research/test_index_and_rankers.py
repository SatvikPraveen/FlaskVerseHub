import numpy as np
import pytest
from hypothesis import given, settings, strategies as st

from app.search.analysis import Analyzer
from app.search.index import Document, InvertedIndex
from app.search.rankers import BM25PlusRanker, BM25Ranker, TFIDFRanker, get_ranker

pytestmark = pytest.mark.research

ANALYZER = Analyzer(stem=False, stopwords=frozenset(), min_length=1)


def docs(*texts: str) -> list[Document]:
    return [Document(i, {"content": text}) for i, text in enumerate(texts)]


@pytest.fixture
def index() -> InvertedIndex:
    return InvertedIndex.build(
        docs("apple banana apple", "banana cherry", "cherry cherry cherry durian", "apple"),
        ANALYZER,
    )


class TestInvertedIndex:
    def test_statistics(self, index: InvertedIndex) -> None:
        assert index.num_docs == 4
        assert index.df("apple") == 2 and index.df("cherry") == 2 and index.df("zzz") == 0
        assert index.total_term_frequency("cherry") == 4
        assert list(index.doc_lengths) == [3.0, 2.0, 4.0, 1.0]
        assert index.avg_doc_length == 2.5
        assert "apple" in index and "zzz" not in index
        assert index.position_of(2) == 2 and index.position_of(99) is None
        assert index.stats()["vocabulary"] == 4

    def test_field_boosts_weight_tf_and_length(self) -> None:
        index = InvertedIndex.build(
            [Document("a", {"title": "apple", "content": "pear"})],
            ANALYZER,
            field_boosts={"title": 3.0},
        )
        assert index.postings["apple"].term_freqs.tolist() == [3.0]
        assert index.doc_lengths.tolist() == [4.0]

    def test_incremental_add(self, index: InvertedIndex) -> None:
        index.add_documents(docs("durian apple"))
        assert index.num_docs == 5 and index.df("durian") == 2 and index.df("apple") == 3

    def test_empty_index(self) -> None:
        index = InvertedIndex(ANALYZER)
        assert index.num_docs == 0 and index.avg_doc_length == 0.0
        assert BM25Ranker().score(index, ["x"]).size == 0


class TestBM25:
    def test_idf_decreases_with_df(self, index: InvertedIndex) -> None:
        ranker = BM25Ranker()
        assert ranker.idf(index, "durian") > ranker.idf(index, "apple") > 0

    def test_tf_saturation_and_ordering(self) -> None:
        index = InvertedIndex.build(docs("x", "x x", "x x x x x x x x", "y"), ANALYZER)
        scores = BM25Ranker(k1=1.2, b=0.0).score(index, ["x"])
        assert scores[0] < scores[1] < scores[2]
        assert scores[3] == 0
        # Marginal gain shrinks: saturation.
        assert (scores[1] - scores[0]) > (scores[2] - scores[1]) / 6

    def test_length_normalisation_controlled_by_b(self) -> None:
        index = InvertedIndex.build(docs("x y", "x y y y y y y y y y"), ANALYZER)
        without = BM25Ranker(b=0.0).score(index, ["x"])
        with_norm = BM25Ranker(b=1.0).score(index, ["x"])
        assert pytest.approx(without[0]) == without[1]
        assert with_norm[0] > with_norm[1]

    def test_query_term_repetition_adds_weight(self, index: InvertedIndex) -> None:
        ranker = BM25Ranker()
        assert ranker.score(index, ["apple", "apple"])[0] == pytest.approx(
            2 * ranker.score(index, ["apple"])[0]
        )

    def test_unknown_terms_ignored(self, index: InvertedIndex) -> None:
        assert np.all(BM25Ranker().score(index, ["zzz"]) == 0)

    def test_invalid_params(self) -> None:
        with pytest.raises(ValueError, match="k1"):
            BM25Ranker(k1=-1)
        with pytest.raises(ValueError, match="k1"):
            BM25Ranker(b=2)
        with pytest.raises(ValueError, match="delta"):
            BM25PlusRanker(delta=-0.1)

    def test_explain_lists_contributions(self, index: InvertedIndex) -> None:
        contributions = BM25Ranker().explain(index, ["apple", "banana", "zzz"], 0)
        assert [c.term for c in contributions] == ["apple", "banana"] or [
            c.term for c in contributions
        ] == ["banana", "apple"]
        total = sum(c.weight for c in contributions)
        assert total == pytest.approx(BM25Ranker().score(index, ["apple", "banana"])[0])
        assert contributions[0].df >= 1 and contributions[0].idf > 0

    @settings(max_examples=40, deadline=None)
    @given(
        corpus=st.lists(
            st.lists(st.sampled_from("abcdef"), min_size=1, max_size=15), min_size=1, max_size=12
        ),
        query=st.lists(st.sampled_from("abcdef"), min_size=1, max_size=4),
        k1=st.floats(min_value=0.0, max_value=3.0),
        b=st.floats(min_value=0.0, max_value=1.0),
    )
    def test_scores_are_finite_and_non_negative(
        self, corpus: list[list[str]], query: list[str], k1: float, b: float
    ) -> None:
        index = InvertedIndex.build(
            docs(*[" ".join(d) for d in corpus]),
            Analyzer(stem=False, stopwords=frozenset(), min_length=1),
        )
        scores = BM25Ranker(k1=k1, b=b).score(index, query)
        assert scores.shape == (len(corpus),)
        assert np.all(np.isfinite(scores)) and np.all(scores >= 0)
        # A document with no query term scores exactly zero.
        for position, doc in enumerate(corpus):
            if not set(doc) & set(query):
                assert scores[position] == 0


class TestBM25Plus:
    def test_delta_lifts_every_matching_document(self, index: InvertedIndex) -> None:
        plain = BM25Ranker().score(index, ["apple"])
        plus = BM25PlusRanker(delta=1.0).score(index, ["apple"])
        matching = plain > 0
        assert np.all(plus[matching] > plain[matching])
        assert np.all(plus[~matching] == 0)
        assert BM25PlusRanker().params() == {"k1": 1.5, "b": 0.75, "delta": 1.0}


class TestTFIDF:
    def test_cosine_bounds_and_self_similarity(self) -> None:
        index = InvertedIndex.build(docs("apple banana", "banana cherry", "durian"), ANALYZER)
        ranker = TFIDFRanker()
        scores = ranker.score(index, ["apple", "banana"])
        assert np.all(scores >= 0) and np.all(scores <= 1.0 + 1e-9)
        assert scores[0] > scores[1] > scores[2] == 0

    def test_norm_cache_invalidates_when_index_grows(self) -> None:
        index = InvertedIndex.build(docs("apple", "banana"), ANALYZER)
        ranker = TFIDFRanker()
        ranker.score(index, ["apple"])
        index.add_documents(docs("apple apple"))
        assert ranker.score(index, ["apple"]).shape == (3,)

    def test_linear_tf_option(self, index: InvertedIndex) -> None:
        assert TFIDFRanker(sublinear_tf=False).params() == {"sublinear_tf": False}
        scores = TFIDFRanker(sublinear_tf=False).score(index, ["cherry"])
        assert scores[2] > scores[1]


def test_get_ranker_registry() -> None:
    assert isinstance(get_ranker("BM25", k1=1.2), BM25Ranker)
    assert isinstance(get_ranker("bm25plus"), BM25PlusRanker)
    assert isinstance(get_ranker("tfidf"), TFIDFRanker)
    assert repr(get_ranker("bm25")) == "BM25Ranker({'k1': 1.5, 'b': 0.75})"
    with pytest.raises(ValueError, match="unknown ranker"):
        get_ranker("lucene")

from typing import Any

import pytest
from flask.testing import FlaskClient

from app.models import KnowledgeItem, User
from app.search import Document, SearchEngine, service as search_service
from tests.conftest import make_item

pytestmark = pytest.mark.research

DOCS = [
    Document(
        "bm25",
        {"title": "BM25 ranking", "content": "probabilistic relevance ranking with saturation"},
    ),
    Document(
        "tfidf",
        {"title": "TF-IDF weighting", "content": "vector space model inverse document frequency"},
    ),
    Document("flask", {"title": "Flask blueprints", "content": "modular application structure"}),
    Document(
        "compare",
        {
            "title": "Ranking functions compared",
            "content": "bm25 and tfidf rankings evaluated with ndcg",
        },
    ),
]


class TestSearchEngine:
    def test_ranks_title_matches_first(self) -> None:
        engine = SearchEngine(DOCS)
        result = engine.search("bm25 ranking")
        assert [h.doc_id for h in result.hits] == ["bm25", "compare"]
        assert result.hits[0].rank == 1 and result.hits[0].score > result.hits[1].score
        assert result.terms == ["bm25", "rank"]
        assert result.total == 2 and result.ranker == "bm25" and result.elapsed_ms >= 0

    def test_pagination_and_filtering(self) -> None:
        engine = SearchEngine(DOCS, ranker="tfidf")
        all_hits = engine.search("ranking bm25 inverse", k=None).hits
        assert len(all_hits) == 3
        page = engine.search("ranking bm25 inverse", k=1, offset=1)
        assert page.hits[0].doc_id == all_hits[1].doc_id and page.total == 3
        filtered = engine.search("ranking bm25 inverse", allowed_doc_ids={"tfidf"})
        assert [h.doc_id for h in filtered.hits] == ["tfidf"] and filtered.total == 1

    def test_empty_and_unknown_queries(self) -> None:
        engine = SearchEngine(DOCS)
        assert engine.search("").hits == []
        assert engine.search("the and of").hits == []
        assert engine.search("quantum").total == 0

    def test_explain_and_suggest(self) -> None:
        engine = SearchEngine(DOCS)
        contributions = engine.explain("bm25 ranking", "bm25")
        assert {c.term for c in contributions} == {"bm25", "rank"}
        assert engine.explain("bm25", "missing") == []
        assert engine.suggest("ran") == ["rank"]
        assert engine.suggest("") == []
        assert engine.stats()["documents"] == 4 and engine.stats()["ranker"] == "bm25"

    def test_custom_ranker_instance(self) -> None:
        from app.search.rankers import BM25PlusRanker

        engine = SearchEngine(DOCS, ranker=BM25PlusRanker(delta=0.5))
        assert engine.ranker.name == "bm25plus"
        assert engine.ranked_ids("flask") == ["flask"]


@pytest.mark.usefixtures("db")
class TestSearchService:
    def test_search_items_respects_visibility_and_rank(
        self, items: list[KnowledgeItem], private_item: KnowledgeItem, user: User, other_user: User
    ) -> None:
        page = search_service.search_items("probabilistic ranking BM25", user=None)
        assert page.items[0].title == "BM25 ranking function"
        assert page.ranker == "bm25" and page.terms and page.elapsed_ms >= 0
        assert page.scores[page.items[0].id] > 0
        hidden = search_service.search_items("Private notes", user=None)
        assert hidden.total == 0
        visible = search_service.search_items("Private notes", user=user)
        assert [i.id for i in visible.items] == [private_item.id]
        assert search_service.search_items("Private notes", user=other_user).total == 0
        assert visible.to_dict()["ranker"] == "bm25"

    def test_index_refreshes_after_changes(self, db: Any, user: User) -> None:
        assert search_service.search_items("zebra", user=user).total == 0
        make_item(db, user, "Zebra migration patterns", content="zebra zebra")
        assert search_service.search_items("zebra", user=user).total == 1
        search_service.invalidate()
        assert search_service.get_engine().index.num_docs >= 1

    def test_suggest_and_explain(self, items: list[KnowledgeItem]) -> None:
        assert "blueprint" in search_service.suggest("blue")
        contributions = search_service.explain("blueprints", items[3])
        assert contributions and contributions[0].term == "blueprint"

    def test_configured_ranker(self, app: Any, items: list[KnowledgeItem]) -> None:
        app.config["SEARCH_RANKER"] = "tfidf"
        search_service.invalidate()
        try:
            assert search_service.search_items("blueprints", user=None).ranker == "tfidf"
        finally:
            app.config["SEARCH_RANKER"] = "bm25"
            search_service.invalidate()

    def test_search_page_renders_scores(
        self, client: FlaskClient, items: list[KnowledgeItem]
    ) -> None:
        html = client.get("/search?q=websockets").get_data(as_text=True)
        assert "WebSockets with SocketIO" in html
        assert "ranked by BM25" in html and "<code>websocket</code>" in html


@pytest.mark.slow
def test_benchmark_search_latency(benchmark: Any) -> None:
    from experiments.corpus import generate_corpus

    corpus = generate_corpus(num_docs=300, num_topics=6, seed=1)
    engine = SearchEngine(corpus.documents)
    query = next(iter(corpus.queries.values()))
    result = benchmark(engine.search, query)
    assert result.total > 0

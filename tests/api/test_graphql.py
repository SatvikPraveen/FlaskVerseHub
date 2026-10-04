from typing import Any

import pytest
from flask.testing import FlaskClient

from app.models import KnowledgeItem, User
from tests.api.conftest import graphql

pytestmark = pytest.mark.api


def test_query_items_and_search(
    client: FlaskClient, items: list[KnowledgeItem], private_item: KnowledgeItem
) -> None:
    payload = graphql(
        client,
        '{ items(perPage: 2, sort: "title") { total pages hasNext items { title slug tags author { username } category { slug } } } }',
    )
    page = payload["data"]["items"]
    assert page["total"] == 5 and page["pages"] == 3 and page["hasNext"] is True
    assert page["items"][0]["title"] == "BM25 ranking function"
    assert page["items"][0]["category"]["slug"] == "fundamentals"
    search = graphql(
        client,
        '{ search(query: "vector space inverse", perPage: 3) { ranker terms total items { title score } } }',
    )["data"]["search"]
    assert search["items"][0]["title"] == "TF-IDF weighting" and search["items"][0]["score"] > 0
    assert search["ranker"] == "bm25" and "vector" in search["terms"]


def test_item_lookup_respects_visibility(
    client: FlaskClient, private_item: KnowledgeItem, user: User, token_for: Any
) -> None:
    anon = graphql(client, f'{{ item(slug: "{private_item.slug}") {{ title }} }}')
    assert anon["data"]["item"] is None
    own = graphql(
        client,
        f'{{ item(slug: "{private_item.slug}") {{ title wordCount readingTime status }} }}',
        headers=token_for(user),
    )
    assert (
        own["data"]["item"]["title"] == "Private notes"
        and own["data"]["item"]["status"] == "published"
    )
    by_id = graphql(
        client, f"{{ item(id: {private_item.id}) {{ slug }} }}", headers=token_for(user)
    )
    assert by_id["data"]["item"]["slug"] == private_item.slug


def test_me_categories_tags_user(
    client: FlaskClient, public_item: KnowledgeItem, user: User, token_for: Any
) -> None:
    anon = graphql(
        client,
        '{ me { username } categories { slug itemCount } tags(limit: 5) { name usageCount } user(username: "alice") { username itemCount } }',
    )
    assert anon["data"]["me"] is None
    assert anon["data"]["categories"][0] == {"slug": "fundamentals", "itemCount": 1}
    assert {t["name"] for t in anon["data"]["tags"]} == {"flask", "architecture"}
    assert anon["data"]["user"]["itemCount"] == 1
    me = graphql(client, "{ me { username isAdmin } }", headers=token_for(user))
    assert me["data"]["me"] == {"username": "alice", "isAdmin": False}


class TestMutations:
    CREATE = """
    mutation Create($input: ItemInput!) {
      createItem(input: $input) { item { slug title tags isPublic version } }
    }"""

    def test_create_update_delete(self, client: FlaskClient, user: User, token_for: Any) -> None:
        headers = token_for(user)
        created = graphql(
            client,
            self.CREATE,
            {
                "input": {
                    "title": "GraphQL item",
                    "content": "Created through GraphQL for testing.",
                    "tags": ["gql", "api"],
                    "isPublic": True,
                }
            },
            headers,
        )
        assert "errors" not in created, created
        item = created["data"]["createItem"]["item"]
        assert item["slug"] == "graphql-item" and sorted(item["tags"]) == ["api", "gql"]
        updated = graphql(
            client,
            'mutation { updateItem(slug: "graphql-item", input: {summary: "Now with a summary"}, changeNote: "add summary") { item { version summary revisions { version note } } } }',
            headers=headers,
        )
        assert updated["data"]["updateItem"]["item"]["version"] == 2
        assert updated["data"]["updateItem"]["item"]["revisions"][0]["note"] == "add summary"
        comment = graphql(
            client,
            'mutation { addComment(slug: "graphql-item", body: "First!") { comment { body author { username } } } }',
            headers=headers,
        )
        assert comment["data"]["addComment"]["comment"]["author"]["username"] == "alice"
        bookmark = graphql(
            client,
            'mutation { toggleBookmark(slug: "graphql-item") { bookmarked } }',
            headers=headers,
        )
        assert bookmark["data"]["toggleBookmark"]["bookmarked"] is True
        deleted = graphql(
            client, 'mutation { deleteItem(slug: "graphql-item") { ok } }', headers=headers
        )
        assert deleted["data"]["deleteItem"]["ok"] is True
        assert graphql(client, '{ item(slug: "graphql-item") { id } }')["data"]["item"] is None

    def test_anonymous_mutation_is_rejected(
        self, client: FlaskClient, public_item: KnowledgeItem
    ) -> None:
        payload = graphql(client, f'mutation {{ deleteItem(slug: "{public_item.slug}") {{ ok }} }}')
        assert payload["data"]["deleteItem"] is None
        assert payload["errors"][0]["message"] == "Authentication required."

    def test_permission_and_validation_errors(
        self, client: FlaskClient, public_item: KnowledgeItem, other_user: User, token_for: Any
    ) -> None:
        headers = token_for(other_user)
        denied = graphql(
            client,
            f'mutation {{ updateItem(slug: "{public_item.slug}", input: {{title: "Hijack attempt"}}) {{ item {{ id }} }} }}',
            headers=headers,
        )
        assert "may not modify" in denied["errors"][0]["message"]
        invalid = graphql(
            client, self.CREATE, {"input": {"title": "x", "content": "short"}}, headers
        )
        assert "Validation failed" in invalid["errors"][0]["message"]
        missing = graphql(
            client,
            'mutation { addComment(slug: "nope", body: "x") { comment { id } } }',
            headers=headers,
        )
        assert "not found" in missing["errors"][0]["message"]
        empty = graphql(
            client,
            f'mutation {{ addComment(slug: "{public_item.slug}", body: "   ") {{ comment {{ id }} }} }}',
            headers=headers,
        )
        assert "must not be empty" in empty["errors"][0]["message"]


def test_malformed_requests(client: FlaskClient) -> None:
    assert client.post("/api/v1/graphql", json={"nope": 1}).status_code == 400
    syntax = graphql(client, "{ items { ")
    assert syntax["errors"]
    via_get = client.get("/api/v1/graphql?query={ categories { slug } }").get_json()
    assert via_get == {"data": {"categories": []}}

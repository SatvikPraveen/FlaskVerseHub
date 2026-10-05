from typing import Any

import pytest
from flask.testing import FlaskClient

from app.models import ApiKey, ItemStatus, KnowledgeItem, User
from tests.conftest import make_item

pytestmark = pytest.mark.api

ITEM = {
    "title": "REST created item",
    "content": "Created through the REST API for testing.",
    "tags": "api, rest",
    "is_public": True,
}


class TestMeta:
    def test_index_lists_endpoints(self, client: FlaskClient) -> None:
        payload = client.get("/api/v1/").get_json()
        assert payload["version"] == "v1"
        assert "/api/v1/items" in payload["endpoints"]

    def test_openapi_document(self, client: FlaskClient) -> None:
        spec = client.get("/api/v1/openapi.json").get_json()
        assert spec["openapi"].startswith("3.1")
        assert "/items/{ident}" in spec["paths"]
        assert spec["components"]["schemas"]["ItemCreateInput"]["required"] == ["title", "content"]
        assert spec["components"]["schemas"]["ItemCreateInput"]["properties"]["difficulty"][
            "enum"
        ] == ["beginner", "intermediate", "advanced", "expert"]
        assert spec["components"]["schemas"]["Item"]["properties"]["author"] == {
            "$ref": "#/components/schemas/User"
        }
        assert "bearerAuth" in spec["components"]["securitySchemes"]

    def test_docs_pages(self, client: FlaskClient) -> None:
        assert b"swagger-ui" in client.get("/api/v1/docs").data
        assert b"graphiql" in client.get("/api/v1/graphql").data

    def test_stats(self, client: FlaskClient, public_item: KnowledgeItem) -> None:
        data = client.get("/api/v1/stats").get_json()["data"]
        assert data["items"] == 1 and data["users"] == 1
        assert data["search_index"]["documents"] == 1

    def test_json_errors_and_no_store(self, client: FlaskClient) -> None:
        response = client.get("/api/v1/items/nope")
        assert response.status_code == 404
        assert response.get_json()["error"] == "not_found"
        assert response.headers["Cache-Control"] == "no-store"


class TestAuth:
    def test_token_flow(self, client: FlaskClient, user: User) -> None:
        response = client.post(
            "/api/v1/auth/token", json={"identifier": user.email, "password": "Password123!"}
        )
        payload = response.get_json()
        assert response.status_code == 200
        assert payload["token_type"] == "Bearer" and payload["user"]["email"] == user.email
        me = client.get(
            "/api/v1/auth/me", headers={"Authorization": f"Bearer {payload['access_token']}"}
        )
        assert me.get_json()["data"]["username"] == "alice"
        refreshed = client.post(
            "/api/v1/auth/refresh", headers={"Authorization": f"Bearer {payload['refresh_token']}"}
        )
        assert refreshed.status_code == 200 and refreshed.get_json()["access_token"]
        # An access token is not a refresh token.
        assert (
            client.post(
                "/api/v1/auth/refresh",
                headers={"Authorization": f"Bearer {payload['access_token']}"},
            ).status_code
            == 401
        )

    def test_bad_credentials_and_validation(self, client: FlaskClient, user: User) -> None:
        assert (
            client.post(
                "/api/v1/auth/token", json={"identifier": "alice", "password": "nope"}
            ).status_code
            == 401
        )
        bad = client.post("/api/v1/auth/token", json={"identifier": "alice"})
        assert bad.status_code == 422 and "password" in bad.get_json()["details"]["fields"]
        assert client.post("/api/v1/auth/token", data="not json").status_code == 400

    def test_invalid_token(self, client: FlaskClient) -> None:
        response = client.get("/api/v1/auth/me", headers={"Authorization": "Bearer garbage"})
        assert response.status_code == 401 and response.get_json()["error"] == "invalid_token"
        assert client.get("/api/v1/auth/me").status_code == 401

    def test_api_key_auth_and_scopes(
        self, client: FlaskClient, db: Any, user: User, api_key_for: Any
    ) -> None:
        read_only = api_key_for(user, ["read"])
        me = client.get("/api/v1/auth/me", headers=read_only)
        assert me.status_code == 200 and me.headers["X-API-Key-Prefix"].startswith("fvh_")
        denied = client.post("/api/v1/items", json=ITEM, headers=read_only)
        assert denied.status_code == 403 and denied.get_json()["error"] == "insufficient_scope"
        assert (
            client.post(
                "/api/v1/items", json=ITEM, headers=api_key_for(user, ["write"])
            ).status_code
            == 201
        )
        assert client.get("/api/v1/auth/me", headers={"X-API-Key": "fvh_bogus"}).status_code == 401
        key = db.session.query(ApiKey).first()
        assert key is not None and key.usage_count >= 1

    def test_inactive_user_rejected(
        self, client: FlaskClient, db: Any, user: User, token_for: Any
    ) -> None:
        headers = token_for(user)
        user.is_active = False
        db.session.commit()
        assert client.get("/api/v1/auth/me", headers=headers).status_code == 401


class TestItems:
    def test_list_respects_visibility_and_filters(
        self, client: FlaskClient, db: Any, user: User, other_user: User, token_for: Any
    ) -> None:
        make_item(db, user, "Public thing", tags="alpha")
        make_item(db, user, "Secret thing", is_public=False)
        make_item(db, other_user, "Draft thing", status=ItemStatus.DRAFT)
        anon = client.get("/api/v1/items").get_json()
        assert [i["title"] for i in anon["data"]] == ["Public thing"]
        assert anon["pagination"]["total"] == 1
        mine = client.get("/api/v1/items?mine=1&sort=title", headers=token_for(user)).get_json()
        assert [i["title"] for i in mine["data"]] == ["Public thing", "Secret thing"]
        assert client.get("/api/v1/items?tag=alpha").get_json()["pagination"]["total"] == 1
        assert client.get("/api/v1/items?per_page=1&page=2").get_json()["pagination"]["pages"] == 1

    def test_crud_cycle(self, client: FlaskClient, user: User, token_for: Any) -> None:
        headers = token_for(user)
        created = client.post("/api/v1/items", json=ITEM, headers=headers)
        assert created.status_code == 201
        data = created.get_json()["data"]
        assert created.headers["Location"] == f"/api/v1/items/{data['slug']}"
        assert sorted(data["tags"]) == ["api", "rest"] and data["version"] == 1
        fetched = client.get(f"/api/v1/items/{data['id']}").get_json()["data"]
        assert fetched["slug"] == data["slug"] and "content" in fetched
        updated = client.patch(
            f"/api/v1/items/{data['slug']}",
            json={"title": "Renamed via API", "change_note": "rename"},
            headers=headers,
        )
        assert updated.status_code == 200 and updated.get_json()["data"]["version"] == 2
        revisions = client.get(f"/api/v1/items/{data['slug']}/revisions").get_json()
        assert revisions["current_version"] == 2 and revisions["data"][0]["note"] == "rename"
        deleted = client.delete(f"/api/v1/items/{data['slug']}", headers=headers)
        assert deleted.status_code == 204
        assert client.get(f"/api/v1/items/{data['slug']}").status_code == 404

    def test_validation_errors(self, client: FlaskClient, user: User, token_for: Any) -> None:
        response = client.post(
            "/api/v1/items",
            json={"title": "x", "difficulty": "impossible"},
            headers=token_for(user),
        )
        assert response.status_code == 422
        fields = response.get_json()["details"]["fields"]
        assert {"title", "content", "difficulty"} <= set(fields)
        assert client.post("/api/v1/items", json=[1, 2], headers=token_for(user)).status_code == 400

    def test_permissions(
        self,
        client: FlaskClient,
        public_item: KnowledgeItem,
        private_item: KnowledgeItem,
        other_user: User,
        admin: User,
        token_for: Any,
    ) -> None:
        assert client.post("/api/v1/items", json=ITEM).status_code == 401
        theirs = token_for(other_user)
        assert (
            client.patch(
                f"/api/v1/items/{public_item.slug}",
                json={"title": "Hijack attempt"},
                headers=theirs,
            ).status_code
            == 403
        )
        forbidden = client.delete(f"/api/v1/items/{public_item.slug}", headers=theirs)
        assert forbidden.status_code == 403
        assert client.get(f"/api/v1/items/{private_item.slug}", headers=theirs).status_code == 404
        assert (
            client.get(f"/api/v1/items/{private_item.slug}", headers=token_for(admin)).status_code
            == 200
        )
        assert (
            client.patch(
                f"/api/v1/items/{public_item.slug}",
                json={"is_featured": True},
                headers=token_for(admin),
            ).get_json()["data"]["is_featured"]
            is True
        )

    def test_comments_and_bookmarks(
        self, client: FlaskClient, public_item: KnowledgeItem, other_user: User, token_for: Any
    ) -> None:
        headers = token_for(other_user)
        created = client.post(
            f"/api/v1/items/{public_item.slug}/comments",
            json={"body": "Nice <i>work</i>"},
            headers=headers,
        )
        assert created.status_code == 201
        assert created.get_json()["data"]["body"] == "Nice &lt;i&gt;work&lt;/i&gt;"
        listed = client.get(f"/api/v1/items/{public_item.slug}/comments").get_json()["data"]
        assert len(listed) == 1 and listed[0]["author"]["username"] == "bob"
        assert (
            client.post(
                f"/api/v1/items/{public_item.slug}/comments", json={"body": ""}, headers=headers
            ).status_code
            == 422
        )
        first = client.post(
            f"/api/v1/items/{public_item.slug}/bookmark", headers=headers
        ).get_json()["data"]
        assert first == {"bookmarked": True, "count": 1}
        assert (
            client.post(f"/api/v1/items/{public_item.slug}/bookmark", headers=headers).get_json()[
                "data"
            ]["bookmarked"]
            is False
        )


class TestSearchAndTaxonomy:
    def test_search_returns_scores_and_terms(
        self, client: FlaskClient, items: list[KnowledgeItem]
    ) -> None:
        payload = client.get("/api/v1/search?q=BM25 probabilistic").get_json()
        assert payload["data"][0]["title"] == "BM25 ranking function"
        assert payload["data"][0]["score"] > 0 and payload["ranker"] == "bm25"
        assert "bm25" in payload["terms"] and payload["pagination"]["total"] >= 1
        assert client.get("/api/v1/search").status_code == 400

    def test_explain_and_suggest(self, client: FlaskClient, items: list[KnowledgeItem]) -> None:
        item = items[0]
        data = client.get(f"/api/v1/items/{item.slug}/explain?q=bm25 saturation").get_json()["data"]
        assert data["score"] > 0 and {t["term"] for t in data["terms"]} == {"bm25", "satur"}
        assert client.get(f"/api/v1/items/{item.slug}/explain").status_code == 400
        assert "blueprint" in client.get("/api/v1/search/suggest?q=blue").get_json()["data"]
        assert client.get("/api/v1/search/suggest").get_json()["data"] == []

    def test_categories_tags_users(
        self, client: FlaskClient, public_item: KnowledgeItem, user: User, token_for: Any
    ) -> None:
        categories = client.get("/api/v1/categories").get_json()["data"]
        assert categories[0]["slug"] == "fundamentals" and categories[0]["item_count"] == 1
        tags = client.get("/api/v1/tags").get_json()
        assert {t["name"] for t in tags["data"]} == {"flask", "architecture"} and tags[
            "pagination"
        ]["total"] == 2
        profile = client.get("/api/v1/users/ALICE").get_json()
        assert profile["data"]["username"] == "alice" and "email" not in profile["data"]
        assert profile["recent_items"][0]["slug"] == public_item.slug
        own = client.get("/api/v1/users/alice", headers=token_for(user)).get_json()
        assert own["data"]["email"] == user.email
        assert client.get("/api/v1/users/ghost").status_code == 404

    def test_activity_scoping(
        self, client: FlaskClient, user: User, other_user: User, admin: User, token_for: Any
    ) -> None:
        token_for(user)  # logs user.login
        token_for(other_user)
        mine = client.get("/api/v1/activity", headers=token_for(user)).get_json()
        assert {row["user"]["username"] for row in mine["data"]} == {"alice"}
        everything = client.get("/api/v1/activity", headers=token_for(admin)).get_json()
        assert {row["user"]["username"] for row in everything["data"]} >= {"alice", "bob", "admin"}
        assert client.get("/api/v1/activity").status_code == 401

from typing import Any

import pytest
from flask.testing import FlaskClient

from app.models import KnowledgeItem, User

pytestmark = pytest.mark.integration


def test_index_renders_counts_and_items(client: FlaskClient, public_item: KnowledgeItem) -> None:
    response = client.get("/")
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert public_item.title in html
    assert "Featured" in html


def test_index_hides_private_items(client: FlaskClient, private_item: KnowledgeItem) -> None:
    assert private_item.title not in client.get("/").get_data(as_text=True)


def test_about_status_tags(client: FlaskClient, public_item: KnowledgeItem) -> None:
    for path in ("/about", "/status", "/tags"):
        assert client.get(path).status_code == 200
    assert "#flask" in client.get("/tags").get_data(as_text=True)


def test_health_probe(client: FlaskClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["status"] == "ok"
    assert payload["checks"]["database"] == "ok"
    assert "version" in payload


def test_search_page(client: FlaskClient, items: list[KnowledgeItem]) -> None:
    assert client.get("/search").status_code == 200
    html = client.get("/search?q=BM25").get_data(as_text=True)
    assert "BM25 ranking function" in html
    assert "TF-IDF weighting" not in html
    assert "No results" in client.get("/search?q=zzzzqqq").get_data(as_text=True)


def test_search_respects_visibility(
    client: FlaskClient, private_item: KnowledgeItem, login: Any, user: User
) -> None:
    assert private_item.title not in client.get("/search?q=Private").get_data(as_text=True)
    login(user)
    assert private_item.title in client.get("/search?q=Private").get_data(as_text=True)


class TestErrorHandling:
    def test_html_404(self, client: FlaskClient) -> None:
        response = client.get("/does-not-exist")
        assert response.status_code == 404
        assert response.mimetype == "text/html"
        assert "Page not found" in response.get_data(as_text=True)

    def test_json_404_for_api_paths(self, client: FlaskClient) -> None:
        response = client.get("/api/v1/does-not-exist")
        assert response.status_code == 404
        payload = response.get_json()
        assert payload["error"] == "not_found"
        assert payload["request_id"]

    def test_json_negotiated_by_accept_header(self, client: FlaskClient) -> None:
        response = client.get("/does-not-exist", headers={"Accept": "application/json"})
        assert response.mimetype == "application/json"

    def test_api_error_class(self, client: FlaskClient) -> None:
        response = client.get("/_test/api-error", headers={"Accept": "application/json"})
        assert response.status_code == 422
        assert response.get_json() == {
            "error": "invalid",
            "message": "nope",
            "status": 422,
            "details": {"field": "x"},
            "request_id": response.headers["X-Request-ID"],
        }

    def test_unexpected_exception_becomes_500(self, app: Any, client: FlaskClient) -> None:
        app.config["PROPAGATE_EXCEPTIONS"] = False
        try:
            response = client.get("/_test/crash")
            assert response.status_code == 500
            assert "Something went wrong" in response.get_data(as_text=True)
            payload = client.get("/_test/crash", headers={"Accept": "application/json"}).get_json()
            assert payload["error"] == "internal_error"
        finally:
            app.config["PROPAGATE_EXCEPTIONS"] = None


class TestObservability:
    def test_request_id_generated_and_propagated(self, client: FlaskClient) -> None:
        generated = client.get("/health").headers["X-Request-ID"]
        assert len(generated) == 32
        echoed = client.get("/health", headers={"X-Request-ID": "abc-123"}).headers["X-Request-ID"]
        assert echoed == "abc-123"

    def test_server_timing_and_security_headers(self, client: FlaskClient) -> None:
        response = client.get("/about")
        assert response.headers["Server-Timing"].startswith("app;dur=")
        assert response.headers["X-Content-Type-Options"] == "nosniff"
        assert response.headers["X-Frame-Options"] == "DENY"
        assert "Content-Security-Policy" in response.headers
        assert "Content-Security-Policy" not in client.get("/health").headers


class TestCli:
    def test_seed_and_users(self, runner: Any) -> None:
        result = runner.invoke(args=["seed", "all"])
        assert result.exit_code == 0, result.output
        assert "items_created" in result.output
        # idempotent
        again = runner.invoke(args=["seed", "demo"])
        assert "'items_created': 0" in again.output
        listing = runner.invoke(args=["users", "list"])
        assert "admin" in listing.output and "3 user(s)" in listing.output

    def test_user_commands(self, runner: Any) -> None:
        created = runner.invoke(
            args=["users", "create", "carol", "carol@example.com", "--password", "Secret123!"]
        )
        assert created.exit_code == 0, created.output
        dup = runner.invoke(
            args=["users", "create", "carol", "x@example.com", "--password", "Secret123!"]
        )
        assert dup.exit_code != 0
        assert runner.invoke(args=["users", "promote", "carol"]).exit_code == 0
        assert runner.invoke(args=["users", "unlock", "carol"]).exit_code == 0
        assert runner.invoke(args=["users", "promote", "ghost"]).exit_code != 0

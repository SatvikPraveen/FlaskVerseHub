from typing import Any

import pytest
from flask.testing import FlaskClient

from app.models import User


@pytest.fixture
def token_for(client: FlaskClient) -> Any:
    def _token(account: User, password: str = "Password123!") -> dict[str, str]:
        response = client.post(
            "/api/v1/auth/token", json={"identifier": account.username, "password": password}
        )
        assert response.status_code == 200, response.get_json()
        return {"Authorization": f"Bearer {response.get_json()['access_token']}"}

    return _token


@pytest.fixture
def api_key_for(app: Any) -> Any:
    from app.auth.service import issue_api_key

    def _key(account: User, scopes: list[str] | None = None) -> dict[str, str]:
        with app.test_request_context():
            _, raw = issue_api_key(account, "test", scopes or ["read", "write"])
        return {"X-API-Key": raw}

    return _key


def graphql(
    client: FlaskClient,
    query: str,
    variables: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
) -> dict[str, Any]:
    response = client.post(
        "/api/v1/graphql", json={"query": query, "variables": variables}, headers=headers or {}
    )
    assert response.status_code == 200
    return response.get_json()

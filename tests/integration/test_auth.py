from typing import Any

import pytest
from flask.testing import FlaskClient

from app.models import ApiKey, User

pytestmark = pytest.mark.integration


class TestRegistration:
    def test_page_renders(self, client: FlaskClient) -> None:
        response = client.get("/auth/register")
        assert response.status_code == 200
        assert "Create your account" in response.get_data(as_text=True)

    def test_successful_registration_logs_in(
        self, client: FlaskClient, db: Any, outbox: list[Any]
    ) -> None:
        response = client.post(
            "/auth/register",
            data={
                "username": "carol",
                "email": "carol@example.com",
                "password": "Password123!",
                "password_confirm": "Password123!",
                "accept_terms": "y",
            },
            follow_redirects=True,
        )
        assert response.status_code == 200
        assert "Welcome aboard" in response.get_data(as_text=True)
        assert db.session.query(User).filter_by(username="carol").one()
        assert len(outbox) == 1
        with client.session_transaction() as session:
            assert session["_user_id"]

    @pytest.mark.parametrize(
        ("field", "value", "message"),
        [
            ("username", "a", "3-64 characters"),
            ("email", "not-an-email", "Invalid email"),
            ("password", "short", "at least 10 characters"),
            ("password", "abcdefghijkl", "Mix letters and numbers"),
            ("password_confirm", "Different123", "Passwords differ"),
        ],
    )
    def test_validation_errors(
        self, client: FlaskClient, field: str, value: str, message: str
    ) -> None:
        data = {
            "username": "carol",
            "email": "carol@example.com",
            "password": "Password123!",
            "password_confirm": "Password123!",
            "accept_terms": "y",
        }
        data[field] = value
        html = client.post("/auth/register", data=data).get_data(as_text=True)
        assert message in html

    def test_duplicate_username(self, client: FlaskClient, user: User) -> None:
        html = client.post(
            "/auth/register",
            data={
                "username": "ALICE",
                "email": "fresh@example.com",
                "password": "Password123!",
                "password_confirm": "Password123!",
                "accept_terms": "y",
            },
        ).get_data(as_text=True)
        assert "username is already taken" in html


class TestLogin:
    def test_page(self, client: FlaskClient) -> None:
        assert "Sign in" in client.get("/auth/login").get_data(as_text=True)

    def test_login_logout_cycle(self, client: FlaskClient, user: User) -> None:
        response = client.post(
            "/auth/login",
            data={"identifier": "alice", "password": "Password123!"},
            follow_redirects=True,
        )
        assert "Signed in as alice" in response.get_data(as_text=True)
        assert client.get("/auth/profile").status_code == 200
        response = client.post("/auth/logout", follow_redirects=True)
        assert "signed out" in response.get_data(as_text=True)
        assert client.get("/auth/profile").status_code == 302

    def test_login_by_email_and_remember(self, client: FlaskClient, user: User) -> None:
        response = client.post(
            "/auth/login",
            data={"identifier": user.email, "password": "Password123!", "remember_me": "y"},
        )
        assert response.status_code == 302
        assert client.get_cookie("remember_token") is not None

    def test_invalid_credentials(self, client: FlaskClient, user: User) -> None:
        html = client.post(
            "/auth/login", data={"identifier": "alice", "password": "nope"}, follow_redirects=True
        ).get_data(as_text=True)
        assert "Invalid username or password" in html

    def test_lockout_message(self, client: FlaskClient, user: User) -> None:
        for _ in range(User.MAX_FAILED_LOGINS):
            client.post("/auth/login", data={"identifier": "alice", "password": "nope"})
        html = client.post(
            "/auth/login",
            data={"identifier": "alice", "password": "Password123!"},
            follow_redirects=True,
        ).get_data(as_text=True)
        assert "temporarily locked" in html

    def test_next_redirect_only_to_local_urls(self, client: FlaskClient, user: User) -> None:
        local = client.post(
            "/auth/login?next=/about", data={"identifier": "alice", "password": "Password123!"}
        )
        assert local.headers["Location"].endswith("/about")
        client.post("/auth/logout")
        external = client.post(
            "/auth/login?next=https://evil.example/x",
            data={"identifier": "alice", "password": "Password123!"},
        )
        assert "evil.example" not in external.headers["Location"]

    def test_logout_requires_post(self, logged_in_client: FlaskClient) -> None:
        assert logged_in_client.get("/auth/logout").status_code == 405


class TestProfile:
    def test_requires_login(self, client: FlaskClient) -> None:
        response = client.get("/auth/profile")
        assert response.status_code == 302
        assert "/auth/login" in response.headers["Location"]

    def test_update_profile(self, logged_in_client: FlaskClient, user: User) -> None:
        response = logged_in_client.post(
            "/auth/profile",
            data={
                "first_name": "Ada",
                "last_name": "L",
                "bio": "Hi",
                "theme": "dark",
                "website": "https://ada.dev",
            },
            follow_redirects=True,
        )
        assert "Profile saved" in response.get_data(as_text=True)
        assert user.full_name == "Ada L"
        assert user.theme == "dark"
        assert user.preference("email_notifications") is False

    def test_change_password(self, logged_in_client: FlaskClient, user: User) -> None:
        bad = logged_in_client.post(
            "/auth/password/change",
            data={
                "current_password": "wrong",
                "new_password": "NewPassword123",
                "confirm": "NewPassword123",
            },
        )
        assert "Current password is incorrect" in bad.get_data(as_text=True)
        good = logged_in_client.post(
            "/auth/password/change",
            data={
                "current_password": "Password123!",
                "new_password": "NewPassword123",
                "confirm": "NewPassword123",
            },
            follow_redirects=True,
        )
        assert "Password changed" in good.get_data(as_text=True)
        assert user.check_password("NewPassword123")

    def test_delete_account(self, logged_in_client: FlaskClient, db: Any, user: User) -> None:
        user_id = user.id
        response = logged_in_client.post(
            "/auth/account/delete", data={"password": "Password123!"}, follow_redirects=True
        )
        assert "account has been deleted" in response.get_data(as_text=True)
        assert db.session.get(User, user_id) is None


class TestPasswordReset:
    def test_full_flow(self, client: FlaskClient, user: User, outbox: list[Any]) -> None:
        response = client.post(
            "/auth/password/reset", data={"identifier": "alice"}, follow_redirects=True
        )
        assert "reset link is on its way" in response.get_data(as_text=True)
        token = outbox[0].body.split("/auth/password/reset/")[1].split()[0]
        assert client.get(f"/auth/password/reset/{token}").status_code == 200
        response = client.post(
            f"/auth/password/reset/{token}",
            data={"password": "Reset-pass-123", "confirm": "Reset-pass-123"},
            follow_redirects=True,
        )
        assert "Password updated" in response.get_data(as_text=True)
        assert user.check_password("Reset-pass-123")
        # Token is now spent.
        assert client.get(f"/auth/password/reset/{token}", follow_redirects=True).status_code == 200
        assert "invalid or has expired" in client.get(
            f"/auth/password/reset/{token}", follow_redirects=True
        ).get_data(as_text=True)

    def test_unknown_account_gets_same_message(
        self, client: FlaskClient, outbox: list[Any]
    ) -> None:
        response = client.post(
            "/auth/password/reset", data={"identifier": "ghost"}, follow_redirects=True
        )
        assert "reset link is on its way" in response.get_data(as_text=True)
        assert outbox == []


class TestEmailVerification:
    def test_verify_and_resend(
        self, logged_in_client: FlaskClient, db: Any, user: User, outbox: list[Any]
    ) -> None:
        user.email_verified = False
        db.session.commit()
        assert (
            logged_in_client.post("/auth/verify/resend", follow_redirects=True).status_code == 200
        )
        token = outbox[0].body.split("/auth/verify/")[1].split()[0]
        html = logged_in_client.get(f"/auth/verify/{token}", follow_redirects=True).get_data(
            as_text=True
        )
        assert "Email verified" in html
        assert user.email_verified
        assert "invalid or has expired" in logged_in_client.get(
            "/auth/verify/bad", follow_redirects=True
        ).get_data(as_text=True)


class TestApiKeys:
    def test_create_list_revoke(self, logged_in_client: FlaskClient, db: Any, user: User) -> None:
        assert logged_in_client.get("/auth/api-keys").status_code == 200
        html = logged_in_client.post(
            "/auth/api-keys", data={"name": "ci", "scopes": ["read", "write"]}
        ).get_data(as_text=True)
        assert "Your new key" in html and "fvh_" in html
        key = db.session.query(ApiKey).filter_by(user_id=user.id).one()
        assert key.scopes == ["read", "write"]
        response = logged_in_client.post(f"/auth/api-keys/{key.id}/revoke", follow_redirects=True)
        assert "API key revoked" in response.get_data(as_text=True)
        assert not key.is_usable
        assert logged_in_client.post("/auth/api-keys/9999/revoke").status_code == 404


class TestDecorators:
    def test_anonymous_gets_401(self, client: FlaskClient) -> None:
        for path in ("/_test/admin", "/_test/role", "/_test/perm"):
            assert client.get(path).status_code == 401
        assert (
            client.get("/_test/admin", headers={"Accept": "application/json"}).get_json()["error"]
            == "unauthorized"
        )

    def test_regular_user_forbidden(self, logged_in_client: FlaskClient) -> None:
        for path in ("/_test/admin", "/_test/role", "/_test/perm"):
            assert logged_in_client.get(path).status_code == 403
        assert logged_in_client.get("/_test/verified").status_code == 200

    def test_admin_passes_everything(self, admin_client: FlaskClient) -> None:
        for path in ("/_test/admin", "/_test/role", "/_test/perm"):
            assert admin_client.get(path).status_code == 200

    def test_role_and_permission_grant(
        self, db: Any, client: FlaskClient, user: User, login: Any
    ) -> None:
        from app.models import Role

        user.roles.append(Role(name="editor", permissions=["items:edit_any"]))
        user.email_verified = False
        db.session.commit()
        login(user)
        assert client.get("/_test/role").status_code == 200
        assert client.get("/_test/perm").status_code == 200
        assert client.get("/_test/admin").status_code == 403
        assert client.get("/_test/verified").status_code == 403

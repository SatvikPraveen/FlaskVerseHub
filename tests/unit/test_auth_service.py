from typing import Any

import pytest
from freezegun import freeze_time

from app.auth import service
from app.auth.tokens import RESET_SALT, generate_token, verify_token
from app.models import Activity, ApiKey, User

pytestmark = [pytest.mark.unit, pytest.mark.usefixtures("db")]


def test_register_user_creates_account_and_sends_verification(app: Any, outbox: list[Any]) -> None:
    with app.test_request_context():
        user = service.register_user("Carol", "Carol@Example.com", "Password123!")
    assert user.id is not None
    assert user.email == "carol@example.com"
    assert user.check_password("Password123!")
    assert len(outbox) == 1
    assert "Verify" in outbox[0].subject
    assert "/auth/verify/" in outbox[0].body
    assert user.activities.filter(Activity.action == "user.registered").count() == 1


def test_register_rejects_duplicates(app: Any, user: User) -> None:
    with app.test_request_context():
        with pytest.raises(service.DuplicateAccountError, match="username"):
            service.register_user(
                "ALICE", "new@example.com", "Password123!", send_verification=False
            )
        with pytest.raises(service.DuplicateAccountError, match="email"):
            service.register_user("someone", user.email, "Password123!", send_verification=False)


def test_find_by_identifier_is_case_insensitive(user: User) -> None:
    assert service.find_by_identifier("ALICE") == user
    assert service.find_by_identifier("Alice@Example.com") == user
    assert service.find_by_identifier("nobody") is None


class TestAuthenticate:
    def test_success_updates_login_stats(self, user: User) -> None:
        result = service.authenticate("alice", "Password123!")
        assert result.ok
        assert user.login_count == 1
        assert user.last_login is not None

    def test_wrong_password_counts_failure(self, user: User) -> None:
        result = service.authenticate("alice", "wrong")
        assert not result.ok
        assert result.failure is service.LoginFailure.INVALID_CREDENTIALS
        assert user.failed_login_attempts == 1

    def test_unknown_user(self) -> None:
        result = service.authenticate("ghost", "x")
        assert result.failure is service.LoginFailure.INVALID_CREDENTIALS
        assert result.user is None

    @freeze_time("2026-05-05 12:00:00")
    def test_lockout_blocks_even_correct_password(self, user: User) -> None:
        for _ in range(User.MAX_FAILED_LOGINS):
            service.authenticate("alice", "wrong")
        assert user.is_locked
        assert service.authenticate("alice", "Password123!").failure is service.LoginFailure.LOCKED

    def test_inactive_account(self, db: Any, user: User) -> None:
        user.is_active = False
        db.session.commit()
        assert (
            service.authenticate("alice", "Password123!").failure is service.LoginFailure.INACTIVE
        )


def test_change_password(user: User) -> None:
    assert not service.change_password(user, "wrong", "NewPassword123")
    assert service.change_password(user, "Password123!", "NewPassword123")
    assert user.check_password("NewPassword123")


class TestPasswordReset:
    def test_request_sends_mail_for_known_account_only(
        self, app: Any, user: User, outbox: list[Any]
    ) -> None:
        with app.test_request_context():
            assert service.request_password_reset("ghost") is False
            assert service.request_password_reset(user.email) is True
        assert len(outbox) == 1
        assert "/auth/password/reset/" in outbox[0].body

    def test_token_is_single_use(self, app: Any, user: User) -> None:
        with app.test_request_context():
            token = generate_token(
                {"uid": user.id, "pw": user.password_hash[-16:]}, salt=RESET_SALT
            )
            assert service.user_for_reset_token(token) == user
            assert service.reset_password(token, "Brand-new-pass1") == user
            assert user.check_password("Brand-new-pass1")
            # The hash changed, so the same token no longer verifies.
            assert service.user_for_reset_token(token) is None
            assert service.reset_password("garbage", "x") is None

    def test_token_expiry(self, app: Any) -> None:
        with app.test_request_context():
            with freeze_time("2026-01-01 00:00:00"):
                token = generate_token({"uid": 1}, salt=RESET_SALT)
            with freeze_time("2026-01-01 00:30:00"):
                assert verify_token(token, salt=RESET_SALT, max_age_seconds=3600) == {"uid": 1}
            with freeze_time("2026-01-01 02:00:00"):
                assert verify_token(token, salt=RESET_SALT, max_age_seconds=3600) is None
            assert verify_token(token, salt="other", max_age_seconds=3600) is None


def test_verify_email_flow(app: Any, user: User, outbox: list[Any]) -> None:
    with app.test_request_context():
        service.send_verification_email(user)
        token = outbox[0].body.split("/auth/verify/")[1].split()[0]
        user.email_verified = False
        assert service.verify_email(token) == user
        assert user.email_verified
        assert service.verify_email("nope") is None


def test_api_key_issue_and_revoke(app: Any, user: User, other_user: User) -> None:
    with app.test_request_context():
        record, raw = service.issue_api_key(user, "ci", ["read", "write"])
        assert ApiKey.lookup(raw) is record
        assert service.revoke_api_key(other_user, record.id) is False
        assert service.revoke_api_key(user, record.id) is True
        assert ApiKey.lookup(raw) is None


def test_delete_account(app: Any, db: Any, user: User) -> None:
    with app.test_request_context():
        assert service.delete_account(user, "wrong") is False
        user_id = user.id
        assert service.delete_account(user, "Password123!") is True
    assert db.session.get(User, user_id) is None

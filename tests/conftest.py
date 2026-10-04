"""Shared pytest fixtures.

The application is created once per session against an in-memory SQLite
database. Tables are created once; after each test every table is emptied,
which isolates tests without paying for ``create_all`` each time and without
relying on SAVEPOINT semantics that pysqlite does not honour by default.
"""

from __future__ import annotations

from collections.abc import Generator, Iterator
from typing import Any, NoReturn

import pytest
from flask import Flask
from flask.testing import FlaskClient, FlaskCliRunner

from app import create_app
from app.extensions import db as _db
from app.models import Category, KnowledgeItem, Role, User

pytest_plugins: list[str] = []


@pytest.fixture(scope="session")
def app() -> Generator[Flask, None, None]:
    application = create_app("testing")
    _register_test_routes(application)
    with application.app_context():
        _db.create_all()
        yield application
        _db.drop_all()


def _register_test_routes(application: Flask) -> None:
    """Test-only wiring: diagnostic routes and per-request login-state reset.

    The session-scoped app context stays pushed for the whole run, so Flask
    reuses it for every test-client request and ``g`` persists between
    requests. Flask-Login caches the resolved user on ``g``; clearing it keeps
    requests independent exactly as they are in production.
    """
    from flask import g

    from app.errors import APIError

    @application.before_request
    def _reset_login_state() -> None:
        g.pop("_login_user", None)

    @application.get("/_test/api-error")
    def _api_error() -> NoReturn:
        raise APIError("nope", 422, code="invalid", details={"field": "x"})

    @application.get("/_test/crash")
    def _crash() -> NoReturn:
        raise RuntimeError("boom")

    from app.auth.decorators import (
        admin_required,
        permission_required,
        role_required,
        verified_required,
    )

    @application.get("/_test/admin")
    @admin_required
    def _admin() -> str:
        return "admin ok"

    @application.get("/_test/role")
    @role_required("editor", "moderator")
    def _role() -> str:
        return "role ok"

    @application.get("/_test/perm")
    @permission_required("items:edit_any")
    def _perm() -> str:
        return "perm ok"

    @application.get("/_test/verified")
    @verified_required
    def _verified() -> str:
        return "verified ok"


@pytest.fixture
def db(app: Flask) -> Generator[Any, None, None]:
    """Database handle whose tables are emptied after the test."""
    try:
        yield _db
    finally:
        _db.session.rollback()
        for table in reversed(_db.metadata.sorted_tables):
            _db.session.execute(table.delete())
        _db.session.commit()
        _db.session.remove()


@pytest.fixture
def client(app: Flask, db: Any) -> FlaskClient:  # db ensures isolation
    return app.test_client()


@pytest.fixture
def runner(app: Flask, db: Any) -> FlaskCliRunner:
    return app.test_cli_runner()


# --------------------------------------------------------------------------- #
# Domain fixtures
# --------------------------------------------------------------------------- #


def make_user(db: Any, username: str = "alice", *, admin: bool = False, **kwargs: Any) -> User:
    user = User(
        username=username,
        email=kwargs.pop("email", f"{username}@example.com"),
        is_admin=admin,
        email_verified=True,
        **kwargs,
    )
    user.set_password(kwargs.get("password", "Password123!"))
    db.session.add(user)
    db.session.commit()
    return user


def make_item(db: Any, author: User, title: str = "Sample item", **kwargs: Any) -> KnowledgeItem:
    tags = kwargs.pop("tags", None)
    item = KnowledgeItem(
        title=title,
        content=kwargs.pop("content", "Flask is a lightweight WSGI web framework. " * 5),
        author=author,
        is_public=kwargs.pop("is_public", True),
        **kwargs,
    )
    if tags:
        item.set_tags(tags)
    db.session.add(item)
    db.session.commit()
    return item


@pytest.fixture
def user(db: Any) -> User:
    return make_user(db, "alice")


@pytest.fixture
def other_user(db: Any) -> User:
    return make_user(db, "bob")


@pytest.fixture
def admin(db: Any) -> User:
    return make_user(db, "admin", admin=True)


@pytest.fixture
def member_role(db: Any) -> Role:
    role = Role(name="member", is_default=True, permissions=["items:create"])
    db.session.add(role)
    db.session.commit()
    return role


@pytest.fixture
def category(db: Any) -> Category:
    category = Category(name="Fundamentals", color="#0d6efd", icon="book")
    db.session.add(category)
    db.session.commit()
    return category


@pytest.fixture
def public_item(db: Any, user: User, category: Category) -> KnowledgeItem:
    return make_item(
        db,
        user,
        "Application factory pattern",
        summary="Build Flask apps with create_app().",
        category=category,
        tags="flask, architecture",
        is_featured=True,
    )


@pytest.fixture
def private_item(db: Any, user: User) -> KnowledgeItem:
    return make_item(db, user, "Private notes", is_public=False, tags="private")


@pytest.fixture
def items(db: Any, user: User, other_user: User, category: Category) -> list[KnowledgeItem]:
    """A small corpus with distinct vocabulary for search tests."""
    corpus = [
        ("BM25 ranking function", "Probabilistic relevance ranking with term saturation.", user),
        ("TF-IDF weighting", "Vector space model with inverse document frequency.", user),
        ("SQLAlchemy relationships", "One-to-many and many-to-many ORM relationships.", other_user),
        ("Flask blueprints", "Modular application structure using blueprints.", other_user),
        ("WebSockets with SocketIO", "Real-time bidirectional events over websockets.", user),
    ]
    created = []
    for title, content, author in corpus:
        created.append(
            make_item(db, author, title, content=content * 3, category=category, summary=content)
        )
    return created


# --------------------------------------------------------------------------- #
# Auth helpers
# --------------------------------------------------------------------------- #


@pytest.fixture
def login(client: FlaskClient) -> Any:
    def _login(account: User) -> None:
        with client.session_transaction() as session:
            session["_user_id"] = str(account.id)
            session["_fresh"] = True

    return _login


@pytest.fixture
def logged_in_client(client: FlaskClient, user: User, login: Any) -> FlaskClient:
    login(user)
    return client


@pytest.fixture
def admin_client(client: FlaskClient, admin: User, login: Any) -> FlaskClient:
    login(admin)
    return client


@pytest.fixture
def auth_headers(app: Flask, user: User) -> dict[str, str]:
    from flask_jwt_extended import create_access_token

    with app.app_context():
        token = create_access_token(identity=str(user.id))
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def outbox(app: Flask) -> Iterator[list[Any]]:
    from app.extensions import mail

    with mail.record_messages() as messages:
        yield messages

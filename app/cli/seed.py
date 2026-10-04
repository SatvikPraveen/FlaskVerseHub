"""Deterministic seed data for development, demos and reproducible experiments."""

from __future__ import annotations

import random

import click
from flask.cli import AppGroup
from sqlalchemy import select

from app.extensions import db
from app.models import Category, Difficulty, KnowledgeItem, Role, User

seed_cli = AppGroup("seed", help="Populate the database with reference and demo data.")

DEFAULT_ROLES: list[dict[str, object]] = [
    {"name": "member", "description": "Default role", "is_default": True,
     "permissions": ["items:create", "items:edit_own", "comments:create"]},
    {"name": "moderator", "description": "Moderates content",
     "permissions": ["items:create", "items:edit_any", "comments:moderate"]},
    {"name": "admin", "description": "Full access", "permissions": ["*"]},
]  # fmt: skip

DEFAULT_CATEGORIES: list[dict[str, str]] = [
    {"name": "Fundamentals", "color": "#0d6efd", "icon": "book",
     "description": "Application factory, blueprints, configuration, templating."},
    {"name": "Data Layer", "color": "#6610f2", "icon": "database",
     "description": "SQLAlchemy models, migrations, query optimisation."},
    {"name": "APIs", "color": "#198754", "icon": "plug",
     "description": "REST design, GraphQL, serialisation, pagination, versioning."},
    {"name": "Security", "color": "#dc3545", "icon": "shield",
     "description": "Authentication, authorisation, CSRF, rate limiting, headers."},
    {"name": "Real-time", "color": "#fd7e14", "icon": "bolt",
     "description": "WebSockets, event-driven updates, background work."},
    {"name": "Operations", "color": "#20c997", "icon": "server",
     "description": "Testing, observability, containers, CI/CD, deployment."},
    {"name": "Research", "color": "#6f42c1", "icon": "flask",
     "description": "Information retrieval, ranking functions, evaluation methodology."},
]  # fmt: skip

_TOPICS: list[tuple[str, str, list[str]]] = [
    ("The application factory pattern", "Fundamentals", ["flask", "architecture", "factory"]),
    ("Organising a large Flask project with blueprints", "Fundamentals", ["flask", "blueprints"]),
    ("Environment-based configuration profiles", "Fundamentals", ["config", "twelve-factor"]),
    ("Jinja template inheritance and macros", "Fundamentals", ["jinja", "templates"]),
    ("Typed models with SQLAlchemy 2.0", "Data Layer", ["sqlalchemy", "typing", "orm"]),
    ("Schema migrations with Alembic", "Data Layer", ["alembic", "migrations"]),
    ("Avoiding the N+1 query problem", "Data Layer", ["sqlalchemy", "performance"]),
    ("Timezone-correct timestamps across SQLite and PostgreSQL", "Data Layer", ["datetime", "utc"]),
    ("Designing a versioned REST API", "APIs", ["rest", "api", "versioning"]),
    ("Cursor versus offset pagination", "APIs", ["pagination", "api", "performance"]),
    ("GraphQL schemas with graphene", "APIs", ["graphql", "graphene"]),
    ("Serialisation contracts with marshmallow", "APIs", ["marshmallow", "serialization"]),
    ("Session versus token authentication", "Security", ["auth", "jwt", "sessions"]),
    ("Role- and permission-based authorisation", "Security", ["rbac", "authorization"]),
    ("Defending against CSRF and XSS", "Security", ["csrf", "xss", "owasp"]),
    ("Rate limiting strategies", "Security", ["rate-limiting", "redis"]),
    ("WebSockets with Flask-SocketIO", "Real-time", ["websockets", "socketio"]),
    ("Event-driven notifications", "Real-time", ["events", "notifications"]),
    ("Structured logging and request correlation", "Operations", ["logging", "observability"]),
    ("Prometheus metrics for Flask", "Operations", ["prometheus", "metrics"]),
    ("Testing Flask applications with pytest", "Operations", ["pytest", "testing"]),
    ("Multi-stage Docker builds for Python", "Operations", ["docker", "deployment"]),
    ("BM25: a probabilistic ranking function", "Research", ["bm25", "ranking", "ir"]),
    ("TF-IDF and the vector space model", "Research", ["tfidf", "vector-space", "ir"]),
    ("Evaluating search with nDCG and MRR", "Research", ["evaluation", "ndcg", "mrr"]),
    ("Building reproducible benchmarks", "Research", ["reproducibility", "benchmark"]),
]

_PARAGRAPHS = [
    "This note explains the concept, shows a minimal implementation, and discusses the trade-offs "
    "that matter when the system grows beyond a toy example.",
    "The approach is compared against the obvious alternative, with attention to correctness, "
    "operational cost, and how easy the resulting code is to test in isolation.",
    "A worked example follows, using the FlaskVerseHub codebase as the reference implementation "
    "so every claim can be verified by reading the source.",
    "Finally, the note lists common pitfalls observed in production systems and how the design "
    "presented here avoids each of them.",
]


def _ensure_roles() -> dict[str, Role]:
    roles: dict[str, Role] = {}
    for spec in DEFAULT_ROLES:
        name = str(spec["name"])
        role = db.session.scalar(select(Role).where(Role.name == name))
        if role is None:
            role = Role(**spec)
            db.session.add(role)
        roles[name] = role
    db.session.flush()
    return roles


def _ensure_categories() -> dict[str, Category]:
    categories: dict[str, Category] = {}
    for spec in DEFAULT_CATEGORIES:
        category = db.session.scalar(select(Category).where(Category.name == spec["name"]))
        if category is None:
            category = Category(**spec)
            db.session.add(category)
        categories[spec["name"]] = category
    db.session.flush()
    return categories


def _ensure_user(username: str, email: str, password: str, *, admin: bool = False) -> User:
    user = db.session.scalar(select(User).where(User.username == username))
    if user is None:
        user = User(username=username, email=email, is_admin=admin, email_verified=True)
        user.set_password(password)
        db.session.add(user)
        db.session.flush()
    return user


def seed_reference_data() -> None:
    """Roles and categories: idempotent, safe for production bootstrap."""
    _ensure_roles()
    _ensure_categories()
    db.session.commit()


def seed_demo_data(*, seed: int = 42, items: int | None = None) -> dict[str, int]:
    """Users and knowledge items. Deterministic for a given ``seed``."""
    rng = random.Random(seed)
    _ensure_roles()
    categories = _ensure_categories()
    admin = _ensure_user("admin", "admin@example.com", "AdminPass123!", admin=True)
    alice = _ensure_user("alice", "alice@example.com", "AlicePass123!")
    bob = _ensure_user("bob", "bob@example.com", "BobPass123!")
    authors = [admin, alice, bob]

    created = 0
    topics = _TOPICS if items is None else (_TOPICS * (items // len(_TOPICS) + 1))[:items]
    for index, (title, category_name, tags) in enumerate(topics):
        full_title = title if index < len(_TOPICS) else f"{title} ({index // len(_TOPICS) + 1})"
        if db.session.scalar(select(KnowledgeItem.id).where(KnowledgeItem.title == full_title)):
            continue
        paragraphs = rng.sample(_PARAGRAPHS, k=rng.randint(2, 4))
        item = KnowledgeItem(
            title=full_title,
            summary=f"{title}: what it is, why it matters, and how FlaskVerseHub applies it.",
            content="\n\n".join(f"<p>{p}</p>" for p in paragraphs),
            author=rng.choice(authors),
            category=categories[category_name],
            is_public=rng.random() > 0.15,
            is_featured=rng.random() > 0.8,
            difficulty=rng.choice(list(Difficulty)),
            view_count=rng.randint(0, 500),
        )
        item.set_tags(tags)
        db.session.add(item)
        created += 1
    db.session.commit()
    return {"users": len(authors), "items_created": created}


@seed_cli.command("reference")
def seed_reference_command() -> None:
    """Create roles and categories (idempotent)."""
    seed_reference_data()
    click.echo("Reference data seeded.")


@seed_cli.command("demo")
@click.option("--seed", default=42, show_default=True, help="Random seed for reproducibility.")
@click.option("--items", default=None, type=int, help="Number of items (default: curated set).")
def seed_demo_command(seed: int, items: int | None) -> None:
    """Create demo users (admin/alice/bob) and knowledge items."""
    summary = seed_demo_data(seed=seed, items=items)
    click.echo(f"Demo data seeded: {summary}")


@seed_cli.command("all")
def seed_all_command() -> None:
    """Reference + demo data."""
    seed_reference_data()
    summary = seed_demo_data()
    click.echo(f"Seeded everything: {summary}")

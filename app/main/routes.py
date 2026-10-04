from __future__ import annotations

import platform
import time
from typing import Any

from flask import Response, current_app, jsonify, render_template, request
from flask_login import current_user
from sqlalchemy import func, select, text

from app.extensions import db
from app.main import bp
from app.models import Category, KnowledgeItem, Tag, User
from app.utils.pagination import page_args, paginate
from app.utils.time import utcnow

_STARTED_AT = time.monotonic()


@bp.get("/")
def index() -> str:
    visible = KnowledgeItem.visible_to(current_user if current_user.is_authenticated else None)
    featured = db.session.scalars(
        visible.where(KnowledgeItem.is_featured.is_(True))
        .order_by(KnowledgeItem.published_at.desc())
        .limit(6)
    ).all()
    recent = db.session.scalars(visible.order_by(KnowledgeItem.created_at.desc()).limit(8)).all()
    categories = db.session.scalars(select(Category).order_by(Category.name)).all()
    stats = {
        "items": db.session.scalar(select(func.count()).select_from(visible.subquery())) or 0,
        "users": db.session.scalar(select(func.count(User.id))) or 0,
        "categories": len(categories),
        "tags": db.session.scalar(select(func.count(Tag.id))) or 0,
    }
    return render_template(
        "main/index.html", featured=featured, recent=recent, categories=categories, stats=stats
    )


@bp.get("/about")
def about() -> str:
    return render_template("main/about.html")


@bp.get("/search")
def search() -> str:
    """Site-wide search page backed by the retrieval engine when available."""
    query = (request.args.get("q") or "").strip()
    page, per_page = page_args()
    results: Any = None
    if query:
        visible = KnowledgeItem.visible_to(current_user if current_user.is_authenticated else None)
        pattern = f"%{query}%"
        stmt = visible.where(
            KnowledgeItem.title.ilike(pattern)
            | KnowledgeItem.summary.ilike(pattern)
            | KnowledgeItem.content.ilike(pattern)
        ).order_by(KnowledgeItem.updated_at.desc())
        results = paginate(stmt, page, per_page)
    return render_template("main/search.html", query=query, results=results)


@bp.get("/health")
def health() -> Response:
    """Liveness + readiness probe. Returns 503 when the database is unreachable."""
    checks: dict[str, Any] = {}
    healthy = True
    try:
        db.session.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception as exc:  # pragma: no cover - requires a broken DB
        checks["database"] = f"error: {exc.__class__.__name__}"
        healthy = False
    payload = {
        "status": "ok" if healthy else "degraded",
        "version": current_app.config.get("APP_VERSION"),
        "build": current_app.config.get("BUILD_SHA"),
        "uptime_seconds": round(time.monotonic() - _STARTED_AT, 1),
        "timestamp": utcnow().isoformat(),
        "checks": checks,
    }
    response = jsonify(payload)
    response.status_code = 200 if healthy else 503
    return response


@bp.get("/status")
def status() -> str:
    info = {
        "version": current_app.config.get("APP_VERSION"),
        "build": current_app.config.get("BUILD_SHA"),
        "environment": current_app.config.get("ENV_NAME"),
        "python": platform.python_version(),
        "database": db.engine.dialect.name,
        "cache": current_app.config.get("CACHE_TYPE"),
        "ranker": current_app.config.get("SEARCH_RANKER"),
        "uptime_seconds": round(time.monotonic() - _STARTED_AT, 1),
    }
    counts = {
        "users": db.session.scalar(select(func.count(User.id))) or 0,
        "items": db.session.scalar(select(func.count(KnowledgeItem.id))) or 0,
        "categories": db.session.scalar(select(func.count(Category.id))) or 0,
        "tags": db.session.scalar(select(func.count(Tag.id))) or 0,
    }
    return render_template("main/status.html", info=info, counts=counts)


@bp.get("/tags")
def tags() -> str:
    page, per_page = page_args(50)
    stmt = select(Tag).order_by(Tag.name)
    return render_template("main/tags.html", page=paginate(stmt, page, per_page))

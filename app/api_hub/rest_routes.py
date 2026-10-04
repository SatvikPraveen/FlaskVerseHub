"""REST API v1.

Conventions
-----------
* Collection responses: ``{"data": [...], "pagination": {...}}``.
* Single resources: ``{"data": {...}}``.
* Errors: ``{"error", "message", "status", "details"?, "request_id"}``
  (see :mod:`app.errors.handlers`).
* Authentication: ``Authorization: Bearer <jwt>`` or ``X-API-Key``.
"""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from flask import Response, current_app, g, jsonify, render_template, request
from flask_jwt_extended import create_access_token, create_refresh_token
from sqlalchemy import func, select

from app.api_hub import bp
from app.api_hub.auth import api_auth, current_api_user, resolve_api_user
from app.api_hub.schemas import (
    ActivitySchema,
    CategorySchema,
    CommentInput,
    CommentSchema,
    ItemCreateInput,
    ItemSchema,
    ItemSummarySchema,
    ItemUpdateInput,
    PaginationSchema,
    RevisionSchema,
    TagSchema,
    TokenInput,
    UserPrivateSchema,
    UserSchema,
    load_or_422,
)
from app.auth import service as auth_service
from app.errors import APIError
from app.extensions import csrf, db, limiter
from app.knowledge_vault import service as vault_service
from app.models import Activity, Category, Comment, KnowledgeItem, Tag, User
from app.search import service as search_service
from app.utils.pagination import Page, page_args, paginate

csrf.exempt(bp)
limiter.limit(lambda: str(current_app.config.get("RATELIMIT_API", "120 per minute")))(bp)


def _collection(page: Page[Any], schema: Any, **extra: Any) -> Response:
    return jsonify(
        {
            "data": schema.dump(page.items, many=True),
            "pagination": PaginationSchema().dump(page.to_dict()),
            **extra,
        }
    )


def _resource(obj: Any, schema: Any, status: int = 200, **extra: Any) -> Response:
    response = jsonify({"data": schema.dump(obj), **extra})
    response.status_code = status
    return response


def _item_or_404(ident: str) -> KnowledgeItem:
    user = current_api_user()
    item = (
        db.session.get(KnowledgeItem, int(ident))
        if ident.isdigit()
        else db.session.scalar(select(KnowledgeItem).where(KnowledgeItem.slug == ident))
    )
    if item is None or not item.is_visible_to(user):
        raise APIError("Knowledge item not found.", 404)
    return item


def _require_edit(item: KnowledgeItem) -> User:
    user = current_api_user()
    if user is None or not vault_service.can_edit(item, user):
        raise APIError("You may not modify this item.", 403)
    return user


# --------------------------------------------------------------------------- #
# Meta
# --------------------------------------------------------------------------- #


@bp.get("/")
def index() -> Response:
    return jsonify(
        {
            "name": current_app.config["APP_NAME"],
            "version": "v1",
            "app_version": current_app.config["APP_VERSION"],
            "documentation": "/api/v1/docs",
            "openapi": "/api/v1/openapi.json",
            "graphql": "/api/v1/graphql",
            "endpoints": sorted(
                {r.rule for r in current_app.url_map.iter_rules() if r.rule.startswith("/api/v1/")}
            ),
        }
    )


@bp.get("/openapi.json")
def openapi() -> Response:
    from app.api_hub.openapi import build_spec

    return jsonify(build_spec())


@bp.get("/docs")
def docs() -> str:
    return render_template("api/swagger.html")


@bp.get("/stats")
def stats() -> Response:
    user = resolve_api_user()
    visible = KnowledgeItem.visible_to(user).subquery()
    return jsonify(
        {
            "data": {
                "items": db.session.scalar(select(func.count()).select_from(visible)) or 0,
                "users": db.session.scalar(select(func.count(User.id))) or 0,
                "categories": db.session.scalar(select(func.count(Category.id))) or 0,
                "tags": db.session.scalar(select(func.count(Tag.id))) or 0,
                "comments": db.session.scalar(select(func.count(Comment.id))) or 0,
                "search_index": search_service.get_engine().stats(),
            }
        }
    )


# --------------------------------------------------------------------------- #
# Auth
# --------------------------------------------------------------------------- #


@bp.post("/auth/token")
@limiter.limit(lambda: str(current_app.config.get("RATELIMIT_AUTH", "10 per minute")))
def token() -> Response:
    payload = load_or_422(TokenInput(), request.get_json(silent=True))
    result = auth_service.authenticate(payload["identifier"], payload["password"])
    if not result.ok or result.user is None:
        code = result.failure.value if result.failure else "invalid_credentials"
        raise APIError("Invalid credentials.", 401, code=code)
    return jsonify(
        {
            "access_token": create_access_token(identity=result.user),
            "refresh_token": create_refresh_token(identity=result.user),
            "token_type": "Bearer",  # nosec B105 - OAuth2 token type, not a secret
            "expires_in": int(current_app.config["JWT_ACCESS_TOKEN_EXPIRES"].total_seconds()),
            "user": UserPrivateSchema().dump(result.user),
        }
    )


@bp.post("/auth/refresh")
def refresh() -> Response:
    user = resolve_api_user(refresh=True)
    if user is None:
        raise APIError("A refresh token is required.", 401)
    return jsonify(
        {
            "access_token": create_access_token(identity=user),
            "token_type": "Bearer",  # nosec B105 - OAuth2 token type, not a secret
            "expires_in": int(current_app.config["JWT_ACCESS_TOKEN_EXPIRES"].total_seconds()),
        }
    )


@bp.get("/auth/me")
@api_auth()
def me() -> Response:
    return _resource(current_api_user(), UserPrivateSchema())


# --------------------------------------------------------------------------- #
# Items
# --------------------------------------------------------------------------- #


@bp.get("/items")
@api_auth(optional=True)
def list_items() -> Response:
    user = current_api_user()
    filters = vault_service.ItemFilters.from_args(request.args, user=user)
    page, per_page = page_args()
    listing = paginate(vault_service.build_listing(filters, user=user), page, per_page)
    return _collection(listing, ItemSummarySchema(), filters=filters.as_query_args())


@bp.post("/items")
@api_auth(scope="write")
def create_item() -> Response:
    data = load_or_422(ItemCreateInput(), request.get_json(silent=True))
    user = current_api_user()
    assert user is not None
    item = vault_service.create_item(data, author=user)
    response = _resource(item, ItemSchema(), 201)
    response.headers["Location"] = f"/api/v1/items/{item.slug}"
    return response


@bp.get("/items/<ident>")
@api_auth(optional=True)
def get_item(ident: str) -> Response:
    item = _item_or_404(ident)
    return _resource(item, ItemSchema())


@bp.route("/items/<ident>", methods=["PATCH", "PUT"])
@api_auth(scope="write")
def update_item(ident: str) -> Response:
    item = _item_or_404(ident)
    user = _require_edit(item)
    data = load_or_422(ItemUpdateInput(), request.get_json(silent=True))
    note = data.pop("change_note", None)
    vault_service.update_item(item, data, actor=user, note=note)
    return _resource(item, ItemSchema())


@bp.delete("/items/<ident>")
@api_auth(scope="write")
def delete_item(ident: str) -> Response:
    item = _item_or_404(ident)
    user = _require_edit(item)
    vault_service.delete_item(item, actor=user)
    return Response(status=204)


@bp.get("/items/<ident>/revisions")
@api_auth(optional=True)
def item_revisions(ident: str) -> Response:
    item = _item_or_404(ident)
    return jsonify(
        {
            "data": RevisionSchema().dump(item.revisions.all(), many=True),
            "current_version": item.version,
        }
    )


@bp.get("/items/<ident>/comments")
@api_auth(optional=True)
def item_comments(ident: str) -> Response:
    item = _item_or_404(ident)
    return jsonify({"data": CommentSchema().dump(item.comments.all(), many=True)})


@bp.post("/items/<ident>/comments")
@api_auth(scope="write")
def add_comment(ident: str) -> Response:
    item = _item_or_404(ident)
    data = load_or_422(CommentInput(), request.get_json(silent=True))
    user = current_api_user()
    assert user is not None
    comment = vault_service.add_comment(
        item, data["body"], author=user, parent_id=data.get("parent_id")
    )
    return _resource(comment, CommentSchema(), 201)


@bp.post("/items/<ident>/bookmark")
@api_auth(scope="write")
def bookmark(ident: str) -> Response:
    item = _item_or_404(ident)
    user = current_api_user()
    assert user is not None
    bookmarked = vault_service.toggle_bookmark(item, user=user)
    return jsonify({"data": {"bookmarked": bookmarked, "count": item.bookmarks.count()}})


@bp.get("/items/<ident>/explain")
@api_auth(optional=True)
def explain(ident: str) -> Response:
    item = _item_or_404(ident)
    query = (request.args.get("q") or "").strip()
    if not query:
        raise APIError("Query parameter 'q' is required.", 400)
    contributions = search_service.explain(query, item)
    return jsonify(
        {
            "data": {
                "item_id": item.id,
                "query": query,
                "ranker": search_service.get_engine().ranker.name,
                "score": round(sum(c.weight for c in contributions), 6),
                "terms": [asdict(c) for c in contributions],
            }
        }
    )


# --------------------------------------------------------------------------- #
# Search, taxonomy, users, activity
# --------------------------------------------------------------------------- #


@bp.get("/search")
@api_auth(optional=True)
def search() -> Response:
    query = (request.args.get("q") or "").strip()
    if not query:
        raise APIError("Query parameter 'q' is required.", 400)
    page, per_page = page_args()
    result = search_service.search_items(
        query, user=current_api_user(), page=page, per_page=per_page
    )
    data = ItemSummarySchema().dump(result.items, many=True)
    for row in data:
        row["score"] = result.scores.get(row["id"])
    return jsonify(
        {
            "data": data,
            "pagination": PaginationSchema().dump(result.to_dict()),
            "query": query,
            "terms": result.terms,
            "ranker": result.ranker,
            "elapsed_ms": result.elapsed_ms,
        }
    )


@bp.get("/search/suggest")
def suggest() -> Response:
    prefix = (request.args.get("q") or "").strip()
    limit = min(max(request.args.get("limit", 8, type=int) or 8, 1), 25)
    return jsonify({"data": search_service.suggest(prefix, limit=limit) if prefix else []})


@bp.get("/categories")
def categories() -> Response:
    rows = db.session.scalars(select(Category).order_by(Category.name)).all()
    return jsonify({"data": CategorySchema().dump(rows, many=True)})


@bp.get("/tags")
def tags() -> Response:
    page, per_page = page_args(50)
    return _collection(paginate(select(Tag).order_by(Tag.name), page, per_page), TagSchema())


@bp.get("/users/<username>")
@api_auth(optional=True)
def user_profile(username: str) -> Response:
    user = db.session.scalar(select(User).where(func.lower(User.username) == username.lower()))
    if user is None:
        raise APIError("User not found.", 404)
    viewer = current_api_user()
    items = db.session.scalars(
        KnowledgeItem.visible_to(viewer)
        .where(KnowledgeItem.author_id == user.id)
        .order_by(KnowledgeItem.updated_at.desc())
        .limit(10)
    ).all()
    schema = (
        UserPrivateSchema()
        if viewer is not None and (viewer.id == user.id or viewer.is_admin)
        else UserSchema()
    )
    return jsonify(
        {"data": schema.dump(user), "recent_items": ItemSummarySchema().dump(items, many=True)}
    )


@bp.get("/activity")
@api_auth()
def activity() -> Response:
    user = current_api_user()
    assert user is not None
    page, per_page = page_args()
    stmt = select(Activity).order_by(Activity.created_at.desc())
    if not user.is_admin:
        stmt = stmt.where(Activity.user_id == user.id)
    return _collection(paginate(stmt, page, per_page), ActivitySchema())


@bp.after_request
def _api_headers(response: Response) -> Response:
    response.headers.setdefault("Cache-Control", "no-store")
    if g.get("api_key") is not None:
        response.headers["X-API-Key-Prefix"] = g.api_key.prefix
    return response

"""GraphQL schema and endpoint (graphene 3).

The schema is a thin projection of the domain services, so authorization
and visibility rules are identical to the REST and HTML interfaces.
"""

from __future__ import annotations

from typing import Any

import graphene
from flask import Response, jsonify, render_template, request
from sqlalchemy import select

from app.api_hub import bp
from app.api_hub.auth import resolve_api_user
from app.errors import APIError
from app.extensions import db
from app.knowledge_vault import service as vault_service
from app.models import (
    Category as CategoryModel,
    KnowledgeItem as ItemModel,
    Tag as TagModel,
    User as UserModel,
)
from app.search import service as search_service
from app.utils.pagination import paginate


def _viewer(info: graphene.ResolveInfo) -> UserModel | None:
    return info.context.get("user")


def _require_user(info: graphene.ResolveInfo) -> UserModel:
    user = _viewer(info)
    if user is None:
        raise PermissionError("Authentication required.")
    return user


class User(graphene.ObjectType):
    id = graphene.Int()
    username = graphene.String()
    full_name = graphene.String()
    bio = graphene.String()
    is_admin = graphene.Boolean()
    item_count = graphene.Int()

    def resolve_item_count(self: Any, info: graphene.ResolveInfo) -> int:
        return int(
            db.session.scalar(
                select(db.func.count()).select_from(
                    ItemModel.visible_to(_viewer(info))
                    .where(ItemModel.author_id == self.id)
                    .subquery()
                )
            )
            or 0
        )


class Category(graphene.ObjectType):
    id = graphene.Int()
    name = graphene.String()
    slug = graphene.String()
    description = graphene.String()
    color = graphene.String()
    item_count = graphene.Int()


class Tag(graphene.ObjectType):
    id = graphene.Int()
    name = graphene.String()
    slug = graphene.String()
    usage_count = graphene.Int()


class Comment(graphene.ObjectType):
    id = graphene.Int()
    body = graphene.String()
    is_deleted = graphene.Boolean()
    parent_id = graphene.Int()
    author = graphene.Field(User)
    created_at = graphene.DateTime()

    def resolve_body(self: Any, _info: graphene.ResolveInfo) -> str:
        return "" if self.is_deleted else str(self.body)


class Revision(graphene.ObjectType):
    version = graphene.Int()
    title = graphene.String()
    summary = graphene.String()
    content = graphene.String()
    note = graphene.String()
    editor = graphene.Field(User)
    created_at = graphene.DateTime()


class Item(graphene.ObjectType):
    id = graphene.Int()
    title = graphene.String()
    slug = graphene.String()
    summary = graphene.String()
    content = graphene.String()
    status = graphene.String()
    difficulty = graphene.String()
    is_public = graphene.Boolean()
    is_featured = graphene.Boolean()
    version = graphene.Int()
    view_count = graphene.Int()
    word_count = graphene.Int()
    reading_time = graphene.Int()
    tags = graphene.List(graphene.String)
    category = graphene.Field(Category)
    author = graphene.Field(User)
    comments = graphene.List(Comment)
    revisions = graphene.List(Revision)
    created_at = graphene.DateTime()
    updated_at = graphene.DateTime()
    score = graphene.Float(description="Relevance score when returned from `search`.")

    def resolve_status(self: Any, _info: graphene.ResolveInfo) -> str:
        return str(self.status.value)

    def resolve_difficulty(self: Any, _info: graphene.ResolveInfo) -> str:
        return str(self.difficulty.value)

    def resolve_tags(self: Any, _info: graphene.ResolveInfo) -> list[str]:
        return list(self.tag_names)

    def resolve_comments(self: Any, _info: graphene.ResolveInfo) -> list[Any]:
        return list(self.comments.all())

    def resolve_revisions(self: Any, _info: graphene.ResolveInfo) -> list[Any]:
        return list(self.revisions.all())

    def resolve_score(self: Any, _info: graphene.ResolveInfo) -> float | None:
        return getattr(self, "_score", None)


class ItemPage(graphene.ObjectType):
    items = graphene.List(Item)
    total = graphene.Int()
    page = graphene.Int()
    pages = graphene.Int()
    has_next = graphene.Boolean()


class SearchResult(graphene.ObjectType):
    items = graphene.List(Item)
    total = graphene.Int()
    terms = graphene.List(graphene.String)
    ranker = graphene.String()
    elapsed_ms = graphene.Float()


class Query(graphene.ObjectType):
    me = graphene.Field(User)
    item = graphene.Field(Item, slug=graphene.String(), id=graphene.Int())
    items = graphene.Field(
        ItemPage,
        page=graphene.Int(default_value=1),
        per_page=graphene.Int(default_value=20),
        q=graphene.String(),
        category=graphene.String(),
        tag=graphene.String(),
        difficulty=graphene.String(),
        mine=graphene.Boolean(default_value=False),
        featured=graphene.Boolean(default_value=False),
        sort=graphene.String(default_value="updated"),
    )
    search = graphene.Field(
        SearchResult,
        query=graphene.String(required=True),
        page=graphene.Int(default_value=1),
        per_page=graphene.Int(default_value=10),
    )
    categories = graphene.List(Category)
    tags = graphene.List(Tag, limit=graphene.Int(default_value=50))
    user = graphene.Field(User, username=graphene.String(required=True))

    def resolve_me(self: Any, info: graphene.ResolveInfo) -> UserModel | None:
        return _viewer(info)

    def resolve_item(
        self: Any, info: graphene.ResolveInfo, slug: str | None = None, id: int | None = None
    ) -> ItemModel | None:
        if slug:
            return vault_service.get_by_slug(slug, user=_viewer(info))
        if id is not None:
            item = db.session.get(ItemModel, id)
            return item if item is not None and item.is_visible_to(_viewer(info)) else None
        return None

    def resolve_items(
        self: Any, info: graphene.ResolveInfo, page: int, per_page: int, **filters: Any
    ) -> dict[str, Any]:
        user = _viewer(info)
        item_filters = vault_service.ItemFilters(
            query=filters.get("q") or None,
            category=filters.get("category") or None,
            tag=filters.get("tag") or None,
            difficulty=filters.get("difficulty") or None,
            mine=bool(filters.get("mine")) and user is not None,
            featured=True if filters.get("featured") else None,
            sort=str(filters.get("sort"))
            if filters.get("sort") in vault_service.SORT_OPTIONS
            else "updated",
        )
        listing = paginate(
            vault_service.build_listing(item_filters, user=user),
            max(1, page),
            max(1, min(per_page, 100)),
        )
        return {
            "items": listing.items,
            "total": listing.total,
            "page": listing.page,
            "pages": listing.pages,
            "has_next": listing.has_next,
        }

    def resolve_search(
        self: Any, info: graphene.ResolveInfo, query: str, page: int, per_page: int
    ) -> dict[str, Any]:
        result = search_service.search_items(
            query, user=_viewer(info), page=max(1, page), per_page=max(1, min(per_page, 100))
        )
        for item in result.items:
            item._score = result.scores.get(item.id)  # type: ignore[attr-defined]
        return {
            "items": result.items,
            "total": result.total,
            "terms": result.terms,
            "ranker": result.ranker,
            "elapsed_ms": result.elapsed_ms,
        }

    def resolve_categories(self: Any, _info: graphene.ResolveInfo) -> list[CategoryModel]:
        return list(db.session.scalars(select(CategoryModel).order_by(CategoryModel.name)).all())

    def resolve_tags(self: Any, _info: graphene.ResolveInfo, limit: int) -> list[TagModel]:
        return list(
            db.session.scalars(
                select(TagModel).order_by(TagModel.name).limit(max(1, min(limit, 500)))
            ).all()
        )

    def resolve_user(self: Any, _info: graphene.ResolveInfo, username: str) -> UserModel | None:
        return db.session.scalar(
            select(UserModel).where(db.func.lower(UserModel.username) == username.lower())
        )


class ItemInput(graphene.InputObjectType):
    title = graphene.String()
    content = graphene.String()
    summary = graphene.String()
    tags = graphene.List(graphene.String)
    category_id = graphene.Int()
    difficulty = graphene.String()
    status = graphene.String()
    source_url = graphene.String()
    is_public = graphene.Boolean()
    is_featured = graphene.Boolean()


def _validate_item_input(data: dict[str, Any], *, creating: bool) -> dict[str, Any]:
    from app.api_hub.schemas import ItemCreateInput, ItemUpdateInput, load_or_422

    return load_or_422(ItemCreateInput() if creating else ItemUpdateInput(), data)


class CreateItem(graphene.Mutation):
    class Arguments:
        input = ItemInput(required=True)

    item = graphene.Field(Item)

    def mutate(self: Any, info: graphene.ResolveInfo, input: ItemInput) -> CreateItem:
        user = _require_user(info)
        data = _validate_item_input(
            {k: v for k, v in dict(input).items() if v is not None}, creating=True
        )
        return CreateItem(item=vault_service.create_item(data, author=user))


class UpdateItem(graphene.Mutation):
    class Arguments:
        slug = graphene.String(required=True)
        input = ItemInput(required=True)
        change_note = graphene.String()

    item = graphene.Field(Item)

    def mutate(
        self: Any,
        info: graphene.ResolveInfo,
        slug: str,
        input: ItemInput,
        change_note: str | None = None,
    ) -> UpdateItem:
        user = _require_user(info)
        item = vault_service.get_by_slug(slug, user=user)
        if item is None:
            raise LookupError("Knowledge item not found.")
        if not vault_service.can_edit(item, user):
            raise PermissionError("You may not modify this item.")
        data = _validate_item_input(
            {k: v for k, v in dict(input).items() if v is not None}, creating=False
        )
        return UpdateItem(item=vault_service.update_item(item, data, actor=user, note=change_note))


class DeleteItem(graphene.Mutation):
    class Arguments:
        slug = graphene.String(required=True)

    ok = graphene.Boolean()

    def mutate(self: Any, info: graphene.ResolveInfo, slug: str) -> DeleteItem:
        user = _require_user(info)
        item = vault_service.get_by_slug(slug, user=user)
        if item is None:
            raise LookupError("Knowledge item not found.")
        if not vault_service.can_edit(item, user):
            raise PermissionError("You may not modify this item.")
        vault_service.delete_item(item, actor=user)
        return DeleteItem(ok=True)


class AddComment(graphene.Mutation):
    class Arguments:
        slug = graphene.String(required=True)
        body = graphene.String(required=True)
        parent_id = graphene.Int()

    comment = graphene.Field(Comment)

    def mutate(
        self: Any, info: graphene.ResolveInfo, slug: str, body: str, parent_id: int | None = None
    ) -> AddComment:
        user = _require_user(info)
        item = vault_service.get_by_slug(slug, user=user)
        if item is None:
            raise LookupError("Knowledge item not found.")
        if not body.strip():
            raise ValueError("Comment body must not be empty.")
        return AddComment(
            comment=vault_service.add_comment(item, body, author=user, parent_id=parent_id)
        )


class ToggleBookmark(graphene.Mutation):
    class Arguments:
        slug = graphene.String(required=True)

    bookmarked = graphene.Boolean()

    def mutate(self: Any, info: graphene.ResolveInfo, slug: str) -> ToggleBookmark:
        user = _require_user(info)
        item = vault_service.get_by_slug(slug, user=user)
        if item is None:
            raise LookupError("Knowledge item not found.")
        return ToggleBookmark(bookmarked=vault_service.toggle_bookmark(item, user=user))


class Mutation(graphene.ObjectType):
    create_item = CreateItem.Field()
    update_item = UpdateItem.Field()
    delete_item = DeleteItem.Field()
    add_comment = AddComment.Field()
    toggle_bookmark = ToggleBookmark.Field()


schema = graphene.Schema(query=Query, mutation=Mutation)


@bp.route("/graphql", methods=["GET", "POST"])
def graphql() -> Response | str:
    if request.method == "GET" and "query" not in request.args:
        return render_template("api/graphiql.html")
    if request.method == "GET":
        query = request.args.get("query", "")
        variables: Any = None
        operation = request.args.get("operationName")
    else:
        payload = request.get_json(silent=True)
        if not isinstance(payload, dict) or not payload.get("query"):
            raise APIError(
                "Body must be a JSON object with a 'query' field.",
                400,
                code="invalid_graphql_request",
            )
        query = str(payload["query"])
        variables = payload.get("variables")
        operation = payload.get("operationName")
    user = resolve_api_user()
    result = schema.execute(
        query, variable_values=variables, operation_name=operation, context_value={"user": user}
    )
    body: dict[str, Any] = {}
    if result.errors:
        body["errors"] = [
            {
                "message": str(getattr(error, "original_error", None) or error),
                "path": list(error.path or []) if getattr(error, "path", None) else None,
            }
            for error in result.errors
        ]
    if result.data is not None:
        body["data"] = result.data
    return jsonify(body)


__all__ = ["schema"]

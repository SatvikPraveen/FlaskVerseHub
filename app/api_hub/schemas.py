"""marshmallow schemas: the API's public contract.

Output schemas (``*Schema``) serialise ORM objects; input schemas
(``*Input``) validate request bodies and raise a 422 problem document with
field-level details on failure.
"""

from __future__ import annotations

from typing import Any

from marshmallow import EXCLUDE, Schema, ValidationError, fields, validate

from app.errors import APIError
from app.models import Difficulty, ItemStatus


class UserSchema(Schema):
    id = fields.Int()
    username = fields.Str()
    full_name = fields.Str()
    bio = fields.Str(allow_none=True)
    avatar_url = fields.Str(allow_none=True)
    is_admin = fields.Bool()
    created_at = fields.DateTime()


class UserPrivateSchema(UserSchema):
    email = fields.Email()
    email_verified = fields.Bool()
    roles = fields.Method("get_roles")
    last_login = fields.DateTime(allow_none=True)

    def get_roles(self, obj: Any) -> list[str]:
        return sorted(obj.role_names)


class CategorySchema(Schema):
    id = fields.Int()
    name = fields.Str()
    slug = fields.Str()
    description = fields.Str(allow_none=True)
    color = fields.Str()
    icon = fields.Str()
    parent_id = fields.Int(allow_none=True)
    item_count = fields.Int()


class TagSchema(Schema):
    id = fields.Int()
    name = fields.Str()
    slug = fields.Str()
    usage_count = fields.Int()


class ItemSummarySchema(Schema):
    id = fields.Int()
    title = fields.Str()
    slug = fields.Str()
    summary = fields.Str(allow_none=True)
    status = fields.Function(lambda o: o.status.value)
    difficulty = fields.Function(lambda o: o.difficulty.value)
    is_public = fields.Bool()
    is_featured = fields.Bool()
    version = fields.Int()
    view_count = fields.Int()
    like_count = fields.Int()
    word_count = fields.Int()
    reading_time = fields.Int()
    tags = fields.Function(lambda o: o.tag_names)
    category = fields.Nested(CategorySchema, only=("id", "name", "slug", "color"), allow_none=True)
    author = fields.Nested(UserSchema, only=("id", "username", "full_name"))
    created_at = fields.DateTime()
    updated_at = fields.DateTime()
    published_at = fields.DateTime(allow_none=True)
    url = fields.Method("get_url")

    def get_url(self, obj: Any) -> str:
        return f"/api/v1/items/{obj.slug}"


class ItemSchema(ItemSummarySchema):
    content = fields.Str()
    source_url = fields.Str(allow_none=True)
    comment_count = fields.Function(lambda o: o.comments.count())
    bookmark_count = fields.Function(lambda o: o.bookmarks.count())


class RevisionSchema(Schema):
    version = fields.Int()
    title = fields.Str()
    summary = fields.Str(allow_none=True)
    content = fields.Str()
    note = fields.Str(allow_none=True)
    editor = fields.Nested(UserSchema, only=("id", "username"), allow_none=True)
    created_at = fields.DateTime()


class CommentSchema(Schema):
    id = fields.Int()
    body = fields.Function(lambda o: "" if o.is_deleted else o.body)
    is_deleted = fields.Bool()
    parent_id = fields.Int(allow_none=True)
    author = fields.Nested(UserSchema, only=("id", "username"))
    created_at = fields.DateTime()


class ActivitySchema(Schema):
    id = fields.Int()
    action = fields.Str()
    resource_type = fields.Str(allow_none=True)
    resource_id = fields.Int(allow_none=True)
    description = fields.Str(allow_none=True)
    extra_data = fields.Dict()
    created_at = fields.DateTime()
    user = fields.Nested(UserSchema, only=("id", "username"), allow_none=True)


class PaginationSchema(Schema):
    page = fields.Int()
    per_page = fields.Int()
    total = fields.Int()
    pages = fields.Int()
    has_next = fields.Bool()
    has_prev = fields.Bool()


# --------------------------------------------------------------------------- #
# Input schemas
# --------------------------------------------------------------------------- #


class _Input(Schema):
    class Meta:
        unknown = EXCLUDE


class TokenInput(_Input):
    identifier = fields.Str(required=True, validate=validate.Length(min=1, max=255))
    password = fields.Str(required=True, load_only=True)


class ItemCreateInput(_Input):
    title = fields.Str(required=True, validate=validate.Length(min=3, max=200))
    content = fields.Str(required=True, validate=validate.Length(min=10))
    summary = fields.Str(allow_none=True, validate=validate.Length(max=500))
    tags = fields.Raw(allow_none=True)
    category_id = fields.Int(allow_none=True)
    difficulty = fields.Str(validate=validate.OneOf([d.value for d in Difficulty]))
    status = fields.Str(validate=validate.OneOf([s.value for s in ItemStatus]))
    source_url = fields.Url(allow_none=True)
    is_public = fields.Bool()
    is_featured = fields.Bool()


class ItemUpdateInput(ItemCreateInput):
    title = fields.Str(validate=validate.Length(min=3, max=200))
    content = fields.Str(validate=validate.Length(min=10))
    change_note = fields.Str(allow_none=True, validate=validate.Length(max=255))


class CommentInput(_Input):
    body = fields.Str(required=True, validate=validate.Length(min=1, max=5000))
    parent_id = fields.Int(allow_none=True)


def load_or_422(schema: Schema, payload: Any) -> dict[str, Any]:
    """Validate ``payload`` (must be a JSON object) or raise a 422 ``APIError``."""
    if not isinstance(payload, dict):
        raise APIError("Request body must be a JSON object.", 400, code="invalid_json")
    try:
        return dict(schema.load(payload))
    except ValidationError as exc:
        raise APIError(
            "Validation failed.", 422, code="validation_error", details={"fields": exc.messages}
        ) from exc


__all__ = [
    "ActivitySchema",
    "CategorySchema",
    "CommentInput",
    "CommentSchema",
    "ItemCreateInput",
    "ItemSchema",
    "ItemSummarySchema",
    "ItemUpdateInput",
    "PaginationSchema",
    "RevisionSchema",
    "TagSchema",
    "TokenInput",
    "UserPrivateSchema",
    "UserSchema",
    "load_or_422",
]

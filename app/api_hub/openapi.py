"""OpenAPI 3.1 document for the REST API, generated from the marshmallow schemas."""

from __future__ import annotations

from typing import Any

from flask import current_app
from marshmallow import Schema, fields

from app.api_hub import schemas as s

_TYPE_MAP: dict[type[fields.Field], dict[str, Any]] = {
    fields.Int: {"type": "integer"},
    fields.Integer: {"type": "integer"},
    fields.Float: {"type": "number"},
    fields.Bool: {"type": "boolean"},
    fields.Boolean: {"type": "boolean"},
    fields.Str: {"type": "string"},
    fields.String: {"type": "string"},
    fields.Email: {"type": "string", "format": "email"},
    fields.Url: {"type": "string", "format": "uri"},
    fields.DateTime: {"type": "string", "format": "date-time"},
    fields.Dict: {"type": "object"},
    fields.Raw: {},
    fields.Function: {},
    fields.Method: {},
}


def _field_schema(field: fields.Field) -> dict[str, Any]:
    if isinstance(field, fields.Nested):
        name = field.schema.__class__.__name__.removesuffix("Schema")
        ref: dict[str, Any] = {"$ref": f"#/components/schemas/{name}"}
        return {"type": "array", "items": ref} if field.many else ref
    if isinstance(field, fields.List):
        return {"type": "array", "items": _field_schema(field.inner)}
    spec = dict(_TYPE_MAP.get(type(field), {"type": "string"}))
    validators = getattr(field, "validate", None)
    for validator in (
        validators if isinstance(validators, list) else ([validators] if validators else [])
    ):
        if hasattr(validator, "choices"):
            spec["enum"] = list(validator.choices)
        if hasattr(validator, "min") and validator.min is not None:
            spec["minLength" if spec.get("type") == "string" else "minimum"] = validator.min
        if hasattr(validator, "max") and validator.max is not None:
            spec["maxLength" if spec.get("type") == "string" else "maximum"] = validator.max
    if field.allow_none:
        spec["nullable"] = True
    return spec


def schema_to_component(schema: Schema) -> dict[str, Any]:
    properties = {name: _field_schema(field) for name, field in schema.fields.items()}
    required = [name for name, field in schema.fields.items() if field.required]
    component: dict[str, Any] = {"type": "object", "properties": properties}
    if required:
        component["required"] = required
    return component


def _ref(name: str) -> dict[str, Any]:
    return {"$ref": f"#/components/schemas/{name}"}


def _collection_response(item: str, extra: dict[str, Any] | None = None) -> dict[str, Any]:
    props: dict[str, Any] = {
        "data": {"type": "array", "items": _ref(item)},
        "pagination": _ref("Pagination"),
    }
    props.update(extra or {})
    return {
        "description": "OK",
        "content": {"application/json": {"schema": {"type": "object", "properties": props}}},
    }


def _resource_response(item: str, description: str = "OK") -> dict[str, Any]:
    return {
        "description": description,
        "content": {
            "application/json": {"schema": {"type": "object", "properties": {"data": _ref(item)}}}
        },
    }


def _body(schema: str) -> dict[str, Any]:
    return {"required": True, "content": {"application/json": {"schema": _ref(schema)}}}


_ERROR = {"description": "Error", "content": {"application/json": {"schema": _ref("Error")}}}
_PAGING = [
    {"name": "page", "in": "query", "schema": {"type": "integer", "minimum": 1, "default": 1}},
    {
        "name": "per_page",
        "in": "query",
        "schema": {"type": "integer", "minimum": 1, "maximum": 100},
    },
]
_IDENT = {
    "name": "ident",
    "in": "path",
    "required": True,
    "schema": {"type": "string"},
    "description": "Numeric id or slug",
}
_SECURED: list[dict[str, list[str]]] = [{"bearerAuth": []}, {"apiKeyAuth": []}]


def build_spec() -> dict[str, Any]:
    components = {
        "User": schema_to_component(s.UserSchema()),
        "UserPrivate": schema_to_component(s.UserPrivateSchema()),
        "Category": schema_to_component(s.CategorySchema()),
        "Tag": schema_to_component(s.TagSchema()),
        "ItemSummary": schema_to_component(s.ItemSummarySchema()),
        "Item": schema_to_component(s.ItemSchema()),
        "Revision": schema_to_component(s.RevisionSchema()),
        "Comment": schema_to_component(s.CommentSchema()),
        "Activity": schema_to_component(s.ActivitySchema()),
        "Pagination": schema_to_component(s.PaginationSchema()),
        "TokenInput": schema_to_component(s.TokenInput()),
        "ItemCreateInput": schema_to_component(s.ItemCreateInput()),
        "ItemUpdateInput": schema_to_component(s.ItemUpdateInput()),
        "CommentInput": schema_to_component(s.CommentInput()),
        "Error": {
            "type": "object",
            "properties": {
                "error": {"type": "string"},
                "message": {"type": "string"},
                "status": {"type": "integer"},
                "details": {"type": "object"},
                "request_id": {"type": "string"},
            },
            "required": ["error", "message", "status"],
        },
    }
    paths: dict[str, Any] = {
        "/": {
            "get": {
                "tags": ["meta"],
                "summary": "API index",
                "responses": {"200": {"description": "OK"}},
            }
        },
        "/stats": {
            "get": {
                "tags": ["meta"],
                "summary": "Content statistics and search-index diagnostics",
                "responses": {"200": {"description": "OK"}},
            }
        },
        "/auth/token": {
            "post": {
                "tags": ["auth"],
                "summary": "Exchange credentials for JWT access and refresh tokens",
                "requestBody": _body("TokenInput"),
                "responses": {
                    "200": {"description": "Tokens issued"},
                    "401": _ERROR,
                    "422": _ERROR,
                },
            }
        },
        "/auth/refresh": {
            "post": {
                "tags": ["auth"],
                "summary": "Issue a new access token from a refresh token",
                "security": [{"bearerAuth": []}],
                "responses": {"200": {"description": "OK"}, "401": _ERROR},
            }
        },
        "/auth/me": {
            "get": {
                "tags": ["auth"],
                "summary": "The authenticated account",
                "security": _SECURED,
                "responses": {"200": _resource_response("UserPrivate"), "401": _ERROR},
            }
        },
        "/items": {
            "get": {
                "tags": ["items"],
                "summary": "List visible knowledge items",
                "security": _SECURED,
                "parameters": [
                    *_PAGING,
                    {
                        "name": "q",
                        "in": "query",
                        "schema": {"type": "string"},
                        "description": "Substring filter",
                    },
                    {
                        "name": "category",
                        "in": "query",
                        "schema": {"type": "string"},
                        "description": "Category slug",
                    },
                    {
                        "name": "tag",
                        "in": "query",
                        "schema": {"type": "string"},
                        "description": "Tag slug",
                    },
                    {
                        "name": "difficulty",
                        "in": "query",
                        "schema": {
                            "type": "string",
                            "enum": ["beginner", "intermediate", "advanced", "expert"],
                        },
                    },
                    {
                        "name": "status",
                        "in": "query",
                        "schema": {"type": "string", "enum": ["draft", "published", "archived"]},
                    },
                    {"name": "mine", "in": "query", "schema": {"type": "boolean"}},
                    {"name": "featured", "in": "query", "schema": {"type": "boolean"}},
                    {
                        "name": "sort",
                        "in": "query",
                        "schema": {
                            "type": "string",
                            "enum": ["updated", "created", "title", "views", "likes"],
                        },
                    },
                ],
                "responses": {"200": _collection_response("ItemSummary")},
            },
            "post": {
                "tags": ["items"],
                "summary": "Create a knowledge item",
                "security": _SECURED,
                "requestBody": _body("ItemCreateInput"),
                "responses": {
                    "201": _resource_response("Item", "Created"),
                    "401": _ERROR,
                    "422": _ERROR,
                },
            },
        },
        "/items/{ident}": {
            "parameters": [_IDENT],
            "get": {
                "tags": ["items"],
                "summary": "Fetch one item",
                "security": _SECURED,
                "responses": {"200": _resource_response("Item"), "404": _ERROR},
            },
            "patch": {
                "tags": ["items"],
                "summary": "Update an item (creates a revision)",
                "security": _SECURED,
                "requestBody": _body("ItemUpdateInput"),
                "responses": {
                    "200": _resource_response("Item"),
                    "403": _ERROR,
                    "404": _ERROR,
                    "422": _ERROR,
                },
            },
            "delete": {
                "tags": ["items"],
                "summary": "Delete an item",
                "security": _SECURED,
                "responses": {"204": {"description": "Deleted"}, "403": _ERROR, "404": _ERROR},
            },
        },
        "/items/{ident}/revisions": {
            "parameters": [_IDENT],
            "get": {
                "tags": ["items"],
                "summary": "Revision history",
                "responses": {"200": {"description": "OK"}},
            },
        },
        "/items/{ident}/comments": {
            "parameters": [_IDENT],
            "get": {
                "tags": ["comments"],
                "summary": "List comments",
                "responses": {"200": {"description": "OK"}},
            },
            "post": {
                "tags": ["comments"],
                "summary": "Add a comment",
                "security": _SECURED,
                "requestBody": _body("CommentInput"),
                "responses": {
                    "201": _resource_response("Comment", "Created"),
                    "401": _ERROR,
                    "422": _ERROR,
                },
            },
        },
        "/items/{ident}/bookmark": {
            "parameters": [_IDENT],
            "post": {
                "tags": ["items"],
                "summary": "Toggle a bookmark",
                "security": _SECURED,
                "responses": {"200": {"description": "OK"}, "401": _ERROR},
            },
        },
        "/items/{ident}/explain": {
            "parameters": [
                _IDENT,
                {"name": "q", "in": "query", "required": True, "schema": {"type": "string"}},
            ],
            "get": {
                "tags": ["search"],
                "summary": "Per-term score explanation for a query",
                "responses": {"200": {"description": "OK"}, "400": _ERROR},
            },
        },
        "/search": {
            "get": {
                "tags": ["search"],
                "summary": "Ranked search (BM25 by default)",
                "security": _SECURED,
                "parameters": [
                    {"name": "q", "in": "query", "required": True, "schema": {"type": "string"}},
                    *_PAGING,
                ],
                "responses": {
                    "200": _collection_response(
                        "ItemSummary",
                        {
                            "query": {"type": "string"},
                            "terms": {"type": "array", "items": {"type": "string"}},
                            "ranker": {"type": "string"},
                            "elapsed_ms": {"type": "number"},
                        },
                    ),
                    "400": _ERROR,
                },
            }
        },
        "/search/suggest": {
            "get": {
                "tags": ["search"],
                "summary": "Vocabulary completions for a prefix",
                "parameters": [
                    {"name": "q", "in": "query", "required": True, "schema": {"type": "string"}},
                    {"name": "limit", "in": "query", "schema": {"type": "integer", "maximum": 25}},
                ],
                "responses": {"200": {"description": "OK"}},
            }
        },
        "/categories": {
            "get": {
                "tags": ["taxonomy"],
                "summary": "All categories",
                "responses": {"200": {"description": "OK"}},
            }
        },
        "/tags": {
            "get": {
                "tags": ["taxonomy"],
                "summary": "Tags (paginated)",
                "parameters": _PAGING,
                "responses": {"200": _collection_response("Tag")},
            }
        },
        "/users/{username}": {
            "parameters": [
                {"name": "username", "in": "path", "required": True, "schema": {"type": "string"}}
            ],
            "get": {
                "tags": ["users"],
                "summary": "Public profile and recent items",
                "security": _SECURED,
                "responses": {"200": {"description": "OK"}, "404": _ERROR},
            },
        },
        "/activity": {
            "get": {
                "tags": ["users"],
                "summary": "Audit trail (own events; all events for admins)",
                "security": _SECURED,
                "parameters": _PAGING,
                "responses": {"200": _collection_response("Activity"), "401": _ERROR},
            }
        },
        "/graphql": {
            "post": {
                "tags": ["graphql"],
                "summary": "GraphQL endpoint (GET serves GraphiQL)",
                "security": _SECURED,
                "responses": {"200": {"description": "OK"}},
            }
        },
    }
    return {
        "openapi": "3.1.0",
        "info": {
            "title": f"{current_app.config['APP_NAME']} API",
            "version": "1.0.0",
            "description": "Versioned REST interface over the FlaskVerseHub knowledge platform. "
            "Authenticate with a JWT bearer token (POST /auth/token) or an API key (X-API-Key).",
            "license": {"name": "MIT", "identifier": "MIT"},
            "contact": {
                "name": "Satvik Praveen",
                "url": "https://github.com/SatvikPraveen/FlaskVerseHub",
            },
        },
        "servers": [{"url": "/api/v1"}],
        "tags": [
            {"name": n}
            for n in ("meta", "auth", "items", "comments", "search", "taxonomy", "users", "graphql")
        ],
        "paths": paths,
        "components": {
            "schemas": components,
            "securitySchemes": {
                "bearerAuth": {"type": "http", "scheme": "bearer", "bearerFormat": "JWT"},
                "apiKeyAuth": {"type": "apiKey", "in": "header", "name": "X-API-Key"},
            },
        },
    }


__all__ = ["build_spec", "schema_to_component"]

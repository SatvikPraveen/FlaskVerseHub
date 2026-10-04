"""API Hub: versioned REST and GraphQL interfaces over the domain services."""

from flask import Blueprint

bp = Blueprint("api_hub", __name__)

from app.api_hub import graphql_routes, rest_routes  # noqa: E402, F401

__all__ = ["bp"]

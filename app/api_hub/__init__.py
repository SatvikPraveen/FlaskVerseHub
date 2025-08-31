# File: app/api_hub/__init__.py
# 🔌 API Hub Blueprint Registration

from flask import Blueprint

api_hub = Blueprint(
    'api_hub',
    __name__,
    url_prefix='/api/v1'
)

from . import rest_routes, graphql_routes
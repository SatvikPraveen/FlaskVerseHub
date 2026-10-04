"""Knowledge Vault: authoring, browsing and curating knowledge items."""

from flask import Blueprint

bp = Blueprint(
    "knowledge_vault",
    __name__,
    static_folder="static",
    static_url_path="/static/vault",
)

from app.knowledge_vault import routes  # noqa: E402, F401

__all__ = ["bp"]

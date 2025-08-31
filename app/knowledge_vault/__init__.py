# File: app/knowledge_vault/__init__.py
# 📚 Knowledge Vault Blueprint Registration

from flask import Blueprint

knowledge_vault = Blueprint(
    'knowledge_vault', 
    __name__,
    template_folder='templates',
    static_folder='static',
    static_url_path='/knowledge_vault/static'
)

from . import routes
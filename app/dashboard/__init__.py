# File: app/dashboard/__init__.py
# 📊 Real-time Dashboard Blueprint Registration

from flask import Blueprint

dashboard = Blueprint(
    'dashboard',
    __name__,
    template_folder='templates',
    static_folder='static',
    static_url_path='/dashboard/static'
)

from . import routes, sockets, events
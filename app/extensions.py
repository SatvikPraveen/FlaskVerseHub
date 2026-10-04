"""Flask extension singletons.

Extensions are instantiated here without an application and bound in
:func:`app.create_app`, which keeps the application factory testable and
allows several app instances per process.
"""

from __future__ import annotations

from flask_caching import Cache
from flask_cors import CORS
from flask_jwt_extended import JWTManager
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_login import LoginManager
from flask_mail import Mail
from flask_migrate import Migrate
from flask_socketio import SocketIO
from flask_sqlalchemy import SQLAlchemy
from flask_wtf.csrf import CSRFProtect
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Typed declarative base shared by every model."""


db = SQLAlchemy(model_class=Base)
migrate = Migrate()
login_manager = LoginManager()
cache = Cache()
mail = Mail()
socketio = SocketIO()
jwt = JWTManager()
cors = CORS()
csrf = CSRFProtect()
limiter = Limiter(key_func=get_remote_address, default_limits=[])

__all__ = [
    "Base",
    "cache",
    "cors",
    "csrf",
    "db",
    "jwt",
    "limiter",
    "login_manager",
    "mail",
    "migrate",
    "socketio",
]

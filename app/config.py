"""Environment-driven configuration.

Every setting is read from the environment with a safe default. Select a
profile with ``FLASK_CONFIG`` (``development`` | ``testing`` | ``production``)
or pass ``config_name`` to :func:`app.create_app`.
"""

from __future__ import annotations

import os
from datetime import timedelta
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


def _env_bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    return int(raw) if raw not in (None, "") else default


def _env_list(name: str, default: list[str]) -> list[str]:
    raw = os.environ.get(name)
    return [item.strip() for item in raw.split(",") if item.strip()] if raw else default


class Config:
    """Base configuration shared by every profile."""

    ENV_NAME = "base"
    APP_NAME = "FlaskVerseHub"
    APP_VERSION = "2.0.0"
    BUILD_SHA = os.environ.get("BUILD_SHA", "dev")

    SECRET_KEY = os.environ.get("SECRET_KEY", "change-me-in-production")

    # Persistence
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL", f"sqlite:///{BASE_DIR / 'instance' / 'flaskversehub.db'}"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_RECORD_QUERIES = True
    SQLALCHEMY_ENGINE_OPTIONS: dict[str, object] = {"pool_pre_ping": True}
    SLOW_QUERY_THRESHOLD_SECONDS = float(os.environ.get("SLOW_QUERY_THRESHOLD_SECONDS", "0.5"))

    # Cache (Flask-Caching backend class names)
    CACHE_TYPE = os.environ.get("CACHE_TYPE", "SimpleCache")
    CACHE_REDIS_URL = os.environ.get("CACHE_REDIS_URL", os.environ.get("REDIS_URL", ""))
    CACHE_DEFAULT_TIMEOUT = _env_int("CACHE_DEFAULT_TIMEOUT", 300)
    CACHE_KEY_PREFIX = "fvh:"

    # Rate limiting
    RATELIMIT_ENABLED = _env_bool("RATELIMIT_ENABLED", True)
    RATELIMIT_STORAGE_URI = os.environ.get("RATELIMIT_STORAGE_URI", "memory://")
    RATELIMIT_HEADERS_ENABLED = True
    RATELIMIT_DEFAULT = os.environ.get("RATELIMIT_DEFAULT", "300 per minute")
    RATELIMIT_AUTH = os.environ.get("RATELIMIT_AUTH", "10 per minute")
    RATELIMIT_API = os.environ.get("RATELIMIT_API", "120 per minute")

    # Sessions and CSRF
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = _env_bool("SESSION_COOKIE_SECURE", False)
    PERMANENT_SESSION_LIFETIME = timedelta(days=_env_int("SESSION_LIFETIME_DAYS", 7))
    REMEMBER_COOKIE_DURATION = timedelta(days=_env_int("REMEMBER_COOKIE_DAYS", 30))
    REMEMBER_COOKIE_HTTPONLY = True
    SESSION_PROTECTION = "strong"
    WTF_CSRF_ENABLED = True
    WTF_CSRF_TIME_LIMIT = None

    # JSON Web Tokens for the API (Flask-JWT-Extended)
    JWT_SECRET_KEY = os.environ.get("JWT_SECRET_KEY", SECRET_KEY)
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(minutes=_env_int("JWT_ACCESS_MINUTES", 60))
    JWT_REFRESH_TOKEN_EXPIRES = timedelta(days=_env_int("JWT_REFRESH_DAYS", 30))
    JWT_TOKEN_LOCATION = ["headers"]
    JWT_HEADER_TYPE = "Bearer"
    JWT_ERROR_MESSAGE_KEY = "error"

    # Mail
    MAIL_SERVER = os.environ.get("MAIL_SERVER", "localhost")
    MAIL_PORT = _env_int("MAIL_PORT", 587)
    MAIL_USE_TLS = _env_bool("MAIL_USE_TLS", True)
    MAIL_USE_SSL = _env_bool("MAIL_USE_SSL", False)
    MAIL_USERNAME = os.environ.get("MAIL_USERNAME")
    MAIL_PASSWORD = os.environ.get("MAIL_PASSWORD")
    MAIL_DEFAULT_SENDER = os.environ.get("MAIL_DEFAULT_SENDER", "noreply@flaskversehub.local")
    MAIL_SUPPRESS_SEND = _env_bool("MAIL_SUPPRESS_SEND", False)

    # Real-time
    SOCKETIO_ASYNC_MODE = os.environ.get("SOCKETIO_ASYNC_MODE", "threading")
    SOCKETIO_MESSAGE_QUEUE = os.environ.get("SOCKETIO_MESSAGE_QUEUE")  # redis URL for multi-worker
    SOCKETIO_CORS_ALLOWED_ORIGINS = _env_list("SOCKETIO_CORS_ALLOWED_ORIGINS", ["*"])

    # CORS for the API
    CORS_ORIGINS = _env_list("CORS_ORIGINS", ["*"])

    # Pagination
    ITEMS_PER_PAGE = _env_int("ITEMS_PER_PAGE", 20)
    MAX_ITEMS_PER_PAGE = _env_int("MAX_ITEMS_PER_PAGE", 100)

    # Uploads
    MAX_CONTENT_LENGTH = _env_int("MAX_CONTENT_LENGTH", 16 * 1024 * 1024)
    UPLOAD_FOLDER = os.environ.get("UPLOAD_FOLDER", str(BASE_DIR / "instance" / "uploads"))
    ALLOWED_UPLOAD_EXTENSIONS = frozenset(
        {"txt", "md", "pdf", "png", "jpg", "jpeg", "gif", "svg", "csv", "json"}
    )

    # Retrieval engine
    SEARCH_RANKER = os.environ.get("SEARCH_RANKER", "bm25")  # bm25 | tfidf
    SEARCH_BM25_K1 = float(os.environ.get("SEARCH_BM25_K1", "1.5"))
    SEARCH_BM25_B = float(os.environ.get("SEARCH_BM25_B", "0.75"))
    SEARCH_INDEX_TTL_SECONDS = _env_int("SEARCH_INDEX_TTL_SECONDS", 60)

    # Observability
    LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO")
    LOG_JSON = _env_bool("LOG_JSON", False)
    METRICS_ENABLED = _env_bool("METRICS_ENABLED", True)
    REQUEST_ID_HEADER = "X-Request-ID"
    SENTRY_DSN = os.environ.get("SENTRY_DSN")

    # Security headers
    SECURITY_HEADERS_ENABLED = _env_bool("SECURITY_HEADERS_ENABLED", True)
    CONTENT_SECURITY_POLICY = os.environ.get(
        "CONTENT_SECURITY_POLICY",
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://cdnjs.cloudflare.com; "
        "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://cdnjs.cloudflare.com "
        "https://fonts.googleapis.com; "
        "font-src 'self' https://fonts.gstatic.com https://cdnjs.cloudflare.com; "
        "img-src 'self' data: https:; connect-src 'self' ws: wss:",
    )

    @classmethod
    def init_app(cls, _app: object) -> None:
        """Profile-specific initialisation hook (called by the factory)."""


class DevelopmentConfig(Config):
    ENV_NAME = "development"
    DEBUG = True
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DEV_DATABASE_URL", f"sqlite:///{BASE_DIR / 'instance' / 'dev.db'}"
    )
    SQLALCHEMY_ECHO = _env_bool("SQLALCHEMY_ECHO", False)
    MAIL_SUPPRESS_SEND = True
    LOG_LEVEL = os.environ.get("LOG_LEVEL", "DEBUG")
    SECURITY_HEADERS_ENABLED = False


class TestingConfig(Config):
    ENV_NAME = "testing"
    TESTING = True
    SECRET_KEY = "testing-secret-key-with-at-least-32-bytes!"  # noqa: S105 - deterministic test secret
    JWT_SECRET_KEY = SECRET_KEY
    SQLALCHEMY_DATABASE_URI = "sqlite://"
    SQLALCHEMY_ENGINE_OPTIONS: dict[str, object] = {
        "connect_args": {"check_same_thread": False},
        "poolclass": None,  # resolved at init to StaticPool for in-memory SQLite
    }
    WTF_CSRF_ENABLED = False
    SESSION_PROTECTION = "basic"
    RATELIMIT_ENABLED = False
    CACHE_TYPE = "NullCache"
    MAIL_SUPPRESS_SEND = True
    METRICS_ENABLED = False
    SECURITY_HEADERS_ENABLED = True
    LOG_LEVEL = "WARNING"
    SEARCH_INDEX_TTL_SECONDS = 0


class ProductionConfig(Config):
    ENV_NAME = "production"
    SESSION_COOKIE_SECURE = _env_bool("SESSION_COOKIE_SECURE", True)
    SESSION_COOKIE_SAMESITE = "Strict"
    PREFERRED_URL_SCHEME = "https"
    CACHE_TYPE = os.environ.get("CACHE_TYPE", "RedisCache")
    RATELIMIT_STORAGE_URI = os.environ.get(
        "RATELIMIT_STORAGE_URI", os.environ.get("REDIS_URL", "memory://")
    )
    LOG_JSON = _env_bool("LOG_JSON", True)
    LOG_LEVEL = os.environ.get("LOG_LEVEL", "WARNING")

    @classmethod
    def init_app(cls, _app: object) -> None:
        if cls.SECRET_KEY == "change-me-in-production":  # noqa: S105
            msg = "SECRET_KEY must be set in production"
            raise RuntimeError(msg)
        if not os.environ.get("DATABASE_URL"):
            msg = "DATABASE_URL must be set in production"
            raise RuntimeError(msg)


CONFIGS: dict[str, type[Config]] = {
    "development": DevelopmentConfig,
    "testing": TestingConfig,
    "production": ProductionConfig,
    "default": DevelopmentConfig,
}


def get_config(name: str | None = None) -> type[Config]:
    """Resolve a configuration class by profile name (case-insensitive)."""
    key = (name or os.environ.get("FLASK_CONFIG") or "default").strip().lower()
    try:
        return CONFIGS[key]
    except KeyError as exc:
        msg = f"unknown configuration profile {key!r}; choose from {sorted(CONFIGS)}"
        raise ValueError(msg) from exc


__all__ = [
    "CONFIGS",
    "Config",
    "DevelopmentConfig",
    "ProductionConfig",
    "TestingConfig",
    "get_config",
]

import pytest

from app import create_app
from app.config import CONFIGS, DevelopmentConfig, ProductionConfig, TestingConfig, get_config

pytestmark = pytest.mark.unit


def test_get_config_resolution() -> None:
    assert get_config("testing") is TestingConfig
    assert get_config("TESTING") is TestingConfig
    assert get_config(None) is CONFIGS["default"]
    with pytest.raises(ValueError, match="unknown configuration profile"):
        get_config("staging")


def test_testing_profile_is_hermetic() -> None:
    assert TestingConfig.TESTING is True
    assert TestingConfig.WTF_CSRF_ENABLED is False
    assert TestingConfig.RATELIMIT_ENABLED is False
    assert TestingConfig.CACHE_TYPE == "NullCache"
    assert TestingConfig.SQLALCHEMY_DATABASE_URI == "sqlite://"


def test_development_profile() -> None:
    assert DevelopmentConfig.DEBUG is True
    assert DevelopmentConfig.MAIL_SUPPRESS_SEND is True


def test_production_requires_secret_and_database(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setattr(ProductionConfig, "SECRET_KEY", "change-me-in-production")
    with pytest.raises(RuntimeError, match="SECRET_KEY"):
        ProductionConfig.init_app(object())
    monkeypatch.setattr(ProductionConfig, "SECRET_KEY", "s3cret")
    with pytest.raises(RuntimeError, match="DATABASE_URL"):
        ProductionConfig.init_app(object())
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://x")
    ProductionConfig.init_app(object())


def test_create_app_applies_overrides() -> None:
    application = create_app("testing", overrides={"ITEMS_PER_PAGE": 7})
    assert application.config["ITEMS_PER_PAGE"] == 7
    assert application.config["ENV_NAME"] == "testing"
    assert "StaticPool" in str(application.config["SQLALCHEMY_ENGINE_OPTIONS"]["poolclass"])

# File: tests/test_config.py
# 🧪 Configuration Testing

import pytest
from app.config import Config, DevelopmentConfig, TestingConfig, ProductionConfig


class TestConfig:
    """Test configuration classes."""
    
    def test_base_config(self):
        """Test base configuration."""
        config = Config()
        
        assert hasattr(config, 'SECRET_KEY')
        assert hasattr(config, 'SQLALCHEMY_DATABASE_URI')
        assert config.SQLALCHEMY_TRACK_MODIFICATIONS == False
        assert config.POSTS_PER_PAGE == 10
        assert config.JWT_EXPIRATION_HOURS == 24
    
    def test_development_config(self):
        """Test development configuration."""
        config = DevelopmentConfig()
        
        assert config.DEBUG == True
        assert config.FLASK_ENV == 'development'
        assert config.SESSION_COOKIE_SECURE == False
        assert config.WTF_CSRF_ENABLED == False
        assert 'sqlite' in config.SQLALCHEMY_DATABASE_URI.lower()
    
    def test_testing_config(self):
        """Test testing configuration."""
        config = TestingConfig()
        
        assert config.TESTING == True
        assert config.FLASK_ENV == 'testing'
        assert config.WTF_CSRF_ENABLED == False
        assert config.CACHE_TYPE == 'null'
        assert config.MAIL_SUPPRESS_SEND == True
        assert config.SQLALCHEMY_DATABASE_URI == 'sqlite:///:memory:'
    
    def test_production_config(self):
        """Test production configuration."""
        config = ProductionConfig()
        
        assert config.DEBUG == False
        assert config.FLASK_ENV == 'production'
        assert config.SESSION_COOKIE_SECURE == True
        assert config.SESSION_COOKIE_HTTPONLY == True
        assert config.SESSION_COOKIE_SAMESITE == 'Strict'
        assert config.CACHE_TYPE == 'redis'
        assert config.LOG_LEVEL == 'WARNING'
    
    def test_config_inheritance(self):
        """Test configuration inheritance."""
        dev_config = DevelopmentConfig()
        prod_config = ProductionConfig()
        
        # Both should inherit from base Config
        assert hasattr(dev_config, 'SECRET_KEY')
        assert hasattr(prod_config, 'SECRET_KEY')
        assert dev_config.POSTS_PER_PAGE == prod_config.POSTS_PER_PAGE
        
        # But have different values for specific settings
        assert dev_config.DEBUG != prod_config.DEBUG
        assert dev_config.SESSION_COOKIE_SECURE != prod_config.SESSION_COOKIE_SECURE
    
    def test_security_settings(self):
        """Test security-related configuration."""
        prod_config = ProductionConfig()
        
        # Security headers should be enabled
        assert prod_config.SESSION_COOKIE_SECURE == True
        assert prod_config.SESSION_COOKIE_HTTPONLY == True
        assert prod_config.SESSION_COOKIE_SAMESITE == 'Strict'
        
        # CSRF should be enabled (not disabled)
        assert not hasattr(prod_config, 'WTF_CSRF_ENABLED') or prod_config.WTF_CSRF_ENABLED != False
    
    def test_database_settings(self):
        """Test database configuration."""
        test_config = TestingConfig()
        dev_config = DevelopmentConfig()
        
        # Testing should use in-memory SQLite
        assert test_config.SQLALCHEMY_DATABASE_URI == 'sqlite:///:memory:'
        
        # Development should use file-based SQLite
        assert 'sqlite:///' in dev_config.SQLALCHEMY_DATABASE_URI
        assert ':memory:' not in dev_config.SQLALCHEMY_DATABASE_URI
        
        # All configs should disable modification tracking
        assert test_config.SQLALCHEMY_TRACK_MODIFICATIONS == False
        assert dev_config.SQLALCHEMY_TRACK_MODIFICATIONS == False
    
    def test_mail_settings(self):
        """Test mail configuration."""
        base_config = Config()
        test_config = TestingConfig()
        
        # Base config should have mail settings
        assert hasattr(base_config, 'MAIL_SERVER')
        assert hasattr(base_config, 'MAIL_PORT')
        assert hasattr(base_config, 'MAIL_USE_TLS')
        
        # Testing should suppress mail sending
        assert test_config.MAIL_SUPPRESS_SEND == True
    
    def test_cache_settings(self):
        """Test cache configuration."""
        dev_config = DevelopmentConfig()
        test_config = TestingConfig()
        prod_config = ProductionConfig()
        
        # Different cache types for different environments
        assert dev_config.CACHE_TYPE == 'simple'
        assert test_config.CACHE_TYPE == 'null'
        assert prod_config.CACHE_TYPE == 'redis'
    
    def test_pagination_settings(self):
        """Test pagination configuration."""
        config = Config()
        
        assert hasattr(config, 'POSTS_PER_PAGE')
        assert isinstance(config.POSTS_PER_PAGE, int)
        assert config.POSTS_PER_PAGE > 0
    
    def test_jwt_settings(self):
        """Test JWT configuration."""
        config = Config()
        
        assert hasattr(config, 'JWT_EXPIRATION_HOURS')
        assert hasattr(config, 'JWT_REFRESH_EXPIRATION_DAYS')
        assert config.JWT_EXPIRATION_HOURS == 24
        assert config.JWT_REFRESH_EXPIRATION_DAYS == 30
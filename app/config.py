# File: FlaskVerseHub/app/config.py

import os
from datetime import timedelta


class Config:
    """Base configuration class."""
    
    # Flask Core Settings
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key-change-this-in-production'
    FLASK_ENV = os.environ.get('FLASK_ENV') or 'production'
    DEBUG = False
    TESTING = False
    
    # Database Configuration
    SQLALCHEMY_DATABASE_URI = (
        os.environ.get('DATABASE_URL') or 
        'sqlite:///' + os.path.join(os.path.dirname(__file__), '..', 'flaskversehub.db')
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_RECORD_QUERIES = True
    SLOW_DB_QUERY_TIME = 0.5
    
    # Redis Configuration
    REDIS_URL = os.environ.get('REDIS_URL') or 'redis://localhost:6379/0'
    
    # Cache Configuration
    CACHE_TYPE = os.environ.get('CACHE_TYPE') or 'redis'
    CACHE_REDIS_URL = os.environ.get('CACHE_REDIS_URL') or 'redis://localhost:6379/1'
    CACHE_DEFAULT_TIMEOUT = 300
    
    # Mail Configuration
    MAIL_SERVER = os.environ.get('MAIL_SERVER') or 'localhost'
    MAIL_PORT = int(os.environ.get('MAIL_PORT') or 587)
    MAIL_USE_TLS = os.environ.get('MAIL_USE_TLS', 'true').lower() in ['true', 'on', '1']
    MAIL_USE_SSL = os.environ.get('MAIL_USE_SSL', 'false').lower() in ['true', 'on', '1']
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME')
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD')
    MAIL_DEFAULT_SENDER = os.environ.get('MAIL_DEFAULT_SENDER') or 'noreply@flaskversehub.com'
    
    # JWT Configuration
    JWT_SECRET_KEY = os.environ.get('JWT_SECRET_KEY') or SECRET_KEY
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=1)
    JWT_REFRESH_TOKEN_EXPIRES = timedelta(days=30)
    JWT_ALGORITHM = 'HS256'
    
    # Security Configuration
    WTF_CSRF_ENABLED = True
    WTF_CSRF_TIME_LIMIT = None
    SESSION_COOKIE_SECURE = False
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    PERMANENT_SESSION_LIFETIME = timedelta(hours=24)
    
    # File Upload Configuration
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB
    UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), '..', 'uploads')
    ALLOWED_EXTENSIONS = {'txt', 'pdf', 'png', 'jpg', 'jpeg', 'gif', 'doc', 'docx', 'csv', 'xlsx'}
    
    # API Configuration
    API_RATE_LIMIT = os.environ.get('API_RATE_LIMIT') or '100 per hour'
    API_RATE_LIMIT_PERIOD = int(os.environ.get('API_RATE_LIMIT_PERIOD') or 3600)
    
    # Pagination Configuration
    ITEMS_PER_PAGE = 20
    MAX_ITEMS_PER_PAGE = 100
    
    # Logging Configuration
    LOG_LEVEL = os.environ.get('LOG_LEVEL') or 'INFO'
    LOG_FILE = os.environ.get('LOG_FILE') or 'logs/flaskversehub.log'
    
    # WebSocket Configuration
    SOCKETIO_ASYNC_MODE = os.environ.get('SOCKETIO_ASYNC_MODE') or 'threading'
    SOCKETIO_PING_TIMEOUT = int(os.environ.get('SOCKETIO_PING_TIMEOUT') or 60)
    SOCKETIO_PING_INTERVAL = int(os.environ.get('SOCKETIO_PING_INTERVAL') or 25)
    
    # External Services Configuration
    RECAPTCHA_PUBLIC_KEY = os.environ.get('RECAPTCHA_PUBLIC_KEY')
    RECAPTCHA_PRIVATE_KEY = os.environ.get('RECAPTCHA_PRIVATE_KEY')
    
    # Application-specific Configuration
    APP_NAME = 'FlaskVerseHub'
    APP_VERSION = '1.0.0'
    BUILD_NUMBER = os.environ.get('BUILD_NUMBER') or 'dev'
    
    @staticmethod
    def init_app(app):
        """Initialize application with this configuration."""
        pass


class DevelopmentConfig(Config):
    """Development configuration."""
    
    DEBUG = True
    FLASK_ENV = 'development'
    
    # Development database (SQLite for simplicity)
    SQLALCHEMY_DATABASE_URI = (
        os.environ.get('DEV_DATABASE_URL') or 
        'sqlite:///' + os.path.join(os.path.dirname(__file__), '..', 'dev_flaskversehub.db')
    )
    
    # Disable CSRF in development for easier testing
    WTF_CSRF_ENABLED = os.environ.get('WTF_CSRF_ENABLED', 'false').lower() in ['true', 'on', '1']
    
    # Less restrictive security in development
    SESSION_COOKIE_SECURE = False
    
    # Development-specific settings
    MAIL_SUPPRESS_SEND = True  # Don't actually send emails in development
    CACHE_TYPE = 'simple'  # Use simple cache instead of Redis in dev
    
    # More verbose logging
    LOG_LEVEL = 'DEBUG'
    SQLALCHEMY_ECHO = True
    
    @staticmethod
    def init_app(app):
        """Initialize development configuration."""
        Config.init_app(app)
        
        # Enable Flask-DebugToolbar if available
        try:
            from flask_debugtoolbar import DebugToolbarExtension
            toolbar = DebugToolbarExtension()
            toolbar.init_app(app)
        except ImportError:
            pass


class TestingConfig(Config):
    """Testing configuration."""
    
    TESTING = True
    WTF_CSRF_ENABLED = False
    
    # Use in-memory SQLite for testing
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    
    # Disable mail sending during tests
    MAIL_SUPPRESS_SEND = True
    
    # Use simple cache for testing
    CACHE_TYPE = 'simple'
    
    # Disable rate limiting during tests
    RATELIMIT_ENABLED = False
    
    # Fast password hashing for tests
    BCRYPT_LOG_ROUNDS = 4
    
    @staticmethod
    def init_app(app):
        """Initialize testing configuration."""
        Config.init_app(app)


class ProductionConfig(Config):
    """Production configuration."""
    
    # Strict security settings
    SESSION_COOKIE_SECURE = True
    SESSION_COOKIE_HTTPONLY = True
    WTF_CSRF_ENABLED = True
    
    # Use PostgreSQL in production
    SQLALCHEMY_DATABASE_URI = (
        os.environ.get('DATABASE_URL') or 
        'postgresql://user:password@localhost/flaskversehub'
    )
    
    # Production logging
    LOG_LEVEL = 'INFO'
    SQLALCHEMY_ECHO = False
    
    # SSL Configuration
    SSL_REDIRECT = os.environ.get('SSL_REDIRECT', 'false').lower() in ['true', 'on', '1']
    
    @staticmethod
    def init_app(app):
        """Initialize production configuration."""
        Config.init_app(app)
        
        # Log to syslog in production
        import logging
        from logging.handlers import SysLogHandler
        
        syslog_handler = SysLogHandler()
        syslog_handler.setLevel(logging.INFO)
        app.logger.addHandler(syslog_handler)


class DockerConfig(ProductionConfig):
    """Docker-specific production configuration."""
    
    @classmethod
    def init_app(cls, app):
        """Initialize Docker configuration."""
        ProductionConfig.init_app(app)
        
        # Log to stdout in Docker
        import logging
        from logging import StreamHandler
        
        stream_handler = StreamHandler()
        stream_handler.setLevel(logging.INFO)
        app.logger.addHandler(stream_handler)


# Configuration mapping
config = {
    'development': DevelopmentConfig,
    'testing': TestingConfig,
    'production': ProductionConfig,
    'docker': DockerConfig,
    'default': DevelopmentConfig
}
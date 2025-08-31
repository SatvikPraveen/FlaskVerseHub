# File: FlaskVerseHub/app/__init__.py

import os
from flask import Flask
from app.extensions import (
    db, migrate, login_manager, cache, mail, socketio, 
    jwt, cors, csrf, limiter
)


def create_app(config_name=None):
    """Create and configure Flask application instance."""
    app = Flask(__name__)
    
    # Load configuration
    config_name = config_name or os.getenv('FLASK_CONFIG', 'development')
    app.config.from_object(f'app.config.{config_name.title()}Config')
    
    # Initialize extensions
    initialize_extensions(app)
    
    # Register blueprints
    register_blueprints(app)
    
    # Register error handlers
    register_error_handlers(app)
    
    # Register shell context
    register_shell_context(app)
    
    # Register template functions
    register_template_functions(app)
    
    return app


def initialize_extensions(app):
    """Initialize Flask extensions."""
    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    cache.init_app(app)
    mail.init_app(app)
    socketio.init_app(app, cors_allowed_origins="*", async_mode='threading')
    jwt.init_app(app)
    cors.init_app(app)
    csrf.init_app(app)
    limiter.init_app(app)
    
    # Configure login manager
    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'Please log in to access this page.'
    login_manager.login_message_category = 'info'
    
    @login_manager.user_loader
    def load_user(user_id):
        from app.models import User
        return User.query.get(int(user_id))


def register_blueprints(app):
    """Register Flask blueprints."""
    # Main/Home blueprint
    from app.main import bp as main_bp
    app.register_blueprint(main_bp)
    
    # Authentication blueprint
    from app.auth import bp as auth_bp
    app.register_blueprint(auth_bp, url_prefix='/auth')
    
    # Knowledge Vault blueprint
    from app.knowledge_vault import bp as knowledge_bp
    app.register_blueprint(knowledge_bp, url_prefix='/knowledge')
    
    # API Hub blueprint
    from app.api_hub import bp as api_bp
    app.register_blueprint(api_bp, url_prefix='/api')
    
    # Dashboard blueprint
    from app.dashboard import bp as dashboard_bp
    app.register_blueprint(dashboard_bp, url_prefix='/dashboard')


def register_error_handlers(app):
    """Register error handlers."""
    from app.errors import handlers
    
    @app.errorhandler(400)
    def bad_request(error):
        return handlers.bad_request(error)
    
    @app.errorhandler(403)
    def forbidden(error):
        return handlers.forbidden(error)
    
    @app.errorhandler(404)
    def not_found(error):
        return handlers.not_found(error)
    
    @app.errorhandler(429)
    def rate_limit_exceeded(error):
        return handlers.rate_limit_exceeded(error)
    
    @app.errorhandler(500)
    def internal_error(error):
        return handlers.internal_error(error)


def register_shell_context(app):
    """Register shell context for flask shell command."""
    @app.shell_context_processor
    def make_shell_context():
        from app import models
        return {
            'db': db,
            'User': models.User,
            'KnowledgeItem': models.KnowledgeItem,
            'Category': models.Category,
            'ApiKey': models.ApiKey,
            'Activity': models.Activity
        }


def register_template_functions(app):
    """Register custom template functions."""
    from datetime import datetime
    
    @app.template_global()
    def moment():
        """Return current moment for template use."""
        return datetime
    
    @app.template_filter('datetime')
    def datetime_filter(value, format='%Y-%m-%d %H:%M'):
        """Format datetime for templates."""
        if value is None:
            return ""
        return value.strftime(format)
    
    @app.template_filter('timeago')
    def timeago_filter(value):
        """Convert datetime to time ago format."""
        if value is None:
            return ""
        
        now = datetime.utcnow()
        diff = now - value
        
        if diff.days > 0:
            return f"{diff.days} day{'s' if diff.days > 1 else ''} ago"
        elif diff.seconds > 3600:
            hours = diff.seconds // 3600
            return f"{hours} hour{'s' if hours > 1 else ''} ago"
        elif diff.seconds > 60:
            minutes = diff.seconds // 60
            return f"{minutes} minute{'s' if minutes > 1 else ''} ago"
        else:
            return "Just now"
    
    @app.template_filter('filesizeformat')
    def filesizeformat_filter(value):
        """Format file size in human readable format."""
        if value is None:
            return ""
        
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if value < 1024.0:
                return f"{value:.1f} {unit}"
            value /= 1024.0
        return f"{value:.1f} PB"
    
    @app.context_processor
    def inject_globals():
        """Inject global variables into templates."""
        from app.models import User
        from flask_login import current_user
        
        # Get knowledge count for current user
        knowledge_count = 0
        if current_user.is_authenticated:
            from app.models import KnowledgeItem
            knowledge_count = KnowledgeItem.query.filter_by(
                created_by=current_user.id
            ).count()
        
        return {
            'config': app.config,
            'knowledge_count': knowledge_count,
            'show_sidebar': True  # Can be dynamic based on route
        }
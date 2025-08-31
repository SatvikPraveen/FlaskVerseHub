#!/bin/bash

# FlaskVerseHub Project Structure Generator
# This script creates the complete directory structure and initial files for FlaskVerseHub

set -e  # Exit on any error

PROJECT_NAME="FlaskVerseHub"
echo "🚀 Generating $PROJECT_NAME project structure..."

# Create main project directory
mkdir -p $PROJECT_NAME
cd $PROJECT_NAME

# Create main app directory structure
echo "📁 Creating app directory structure..."
mkdir -p app/{templates/{macros,shared_components},static/{css,js,images/{banners,icons}}}
mkdir -p app/{knowledge_vault,api_hub,dashboard,auth,utils,security,errors,cli}

# Create blueprint subdirectories
echo "📁 Creating blueprint structures..."

# Knowledge Vault Blueprint
mkdir -p app/knowledge_vault/{templates,static/{css,js,images},tests}

# API Hub Blueprint  
mkdir -p app/api_hub/{docs,tests}

# Dashboard Blueprint
mkdir -p app/dashboard/{templates,static/{css,js,images},tests}

# Auth Blueprint
mkdir -p app/auth/{templates,tests}

# Error handling
mkdir -p app/errors/templates

# Create additional directories
echo "📁 Creating additional directories..."
mkdir -p {migrations/versions,tests/integration,docs,scripts,docker}
mkdir -p .github/workflows
mkdir -p requirements

# Create main application files
echo "📄 Creating main application files..."

# Main app factory
cat > app/__init__.py << 'EOF'
"""
FlaskVerseHub - Complete Flask Mastery Project
App Factory Pattern Implementation
"""
from flask import Flask
from flask_migrate import Migrate

from app.extensions import (
    db, login_manager, cache, mail, socketio, 
    csrf, limiter, migrate
)
from app.config import Config


def create_app(config_class=Config):
    """Application factory pattern"""
    app = Flask(__name__)
    app.config.from_object(config_class)
    
    # Initialize extensions
    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    cache.init_app(app)
    mail.init_app(app)
    socketio.init_app(app, cors_allowed_origins="*")
    csrf.init_app(app)
    limiter.init_app(app)
    
    # Register blueprints
    from app.knowledge_vault import bp as knowledge_bp
    from app.api_hub import bp as api_bp
    from app.dashboard import bp as dashboard_bp
    from app.auth import bp as auth_bp
    from app.errors import bp as errors_bp
    
    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(knowledge_bp, url_prefix='/vault')
    app.register_blueprint(api_bp, url_prefix='/api')
    app.register_blueprint(dashboard_bp, url_prefix='/dashboard')
    app.register_blueprint(errors_bp)
    
    # Register CLI commands
    from app.cli import db_commands, user_commands
    app.register_blueprint(db_commands.bp)
    app.register_blueprint(user_commands.bp)
    
    return app


# Import models to ensure they are registered with SQLAlchemy
from app import models
EOF

# Extensions file
cat > app/extensions.py << 'EOF'
"""
Flask Extensions Initialization
Demonstrates proper extension management in Flask
"""
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager
from flask_mail import Mail
from flask_caching import Cache
from flask_socketio import SocketIO
from flask_wtf.csrf import CSRFProtect
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

# Initialize extensions
db = SQLAlchemy()
migrate = Migrate()
login_manager = LoginManager()
mail = Mail()
cache = Cache()
socketio = SocketIO()
csrf = CSRFProtect()
limiter = Limiter(key_func=get_remote_address)

# Configure Login Manager
login_manager.login_view = 'auth.login'
login_manager.login_message = 'Please log in to access this page.'
login_manager.login_message_category = 'info'
EOF

# Configuration file
cat > app/config.py << 'EOF'
"""
Configuration Classes for Different Environments
Demonstrates Flask configuration best practices
"""
import os
from datetime import timedelta


class Config:
    """Base configuration class"""
    # Flask Core
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key-change-in-production'
    
    # Database
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
        'sqlite:///flaskversehub.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_RECORD_QUERIES = True
    
    # Mail Configuration
    MAIL_SERVER = os.environ.get('MAIL_SERVER') or 'localhost'
    MAIL_PORT = int(os.environ.get('MAIL_PORT') or 587)
    MAIL_USE_TLS = os.environ.get('MAIL_USE_TLS') or True
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME')
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD')
    MAIL_DEFAULT_SENDER = os.environ.get('MAIL_DEFAULT_SENDER')
    
    # Caching
    CACHE_TYPE = os.environ.get('CACHE_TYPE') or 'simple'
    CACHE_REDIS_URL = os.environ.get('REDIS_URL')
    
    # Security
    JWT_SECRET_KEY = os.environ.get('JWT_SECRET_KEY') or SECRET_KEY
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=1)
    JWT_REFRESH_TOKEN_EXPIRES = timedelta(days=30)
    
    # Rate Limiting
    RATELIMIT_STORAGE_URL = os.environ.get('REDIS_URL') or 'memory://'
    
    # Pagination
    POSTS_PER_PAGE = 10
    API_ITEMS_PER_PAGE = 20


class DevelopmentConfig(Config):
    """Development configuration"""
    DEBUG = True
    TESTING = False


class TestingConfig(Config):
    """Testing configuration"""
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    WTF_CSRF_ENABLED = False


class ProductionConfig(Config):
    """Production configuration"""
    DEBUG = False
    TESTING = False


# Configuration dictionary
config = {
    'development': DevelopmentConfig,
    'testing': TestingConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}
EOF

# Models file
cat > app/models.py << 'EOF'
"""
SQLAlchemy Models - Centralized Model Definitions
Demonstrates Flask-SQLAlchemy relationships and best practices
"""
from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from app.extensions import db


# Association table for many-to-many relationship
user_roles = db.Table('user_roles',
    db.Column('user_id', db.Integer, db.ForeignKey('user.id'), primary_key=True),
    db.Column('role_id', db.Integer, db.ForeignKey('role.id'), primary_key=True)
)


class User(UserMixin, db.Model):
    """User model with authentication capabilities"""
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    first_name = db.Column(db.String(50), nullable=False)
    last_name = db.Column(db.String(50), nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_login = db.Column(db.DateTime)
    
    # Relationships
    vault_entries = db.relationship('VaultEntry', backref='author', lazy='dynamic')
    roles = db.relationship('Role', secondary=user_roles, backref='users')
    
    def set_password(self, password):
        """Hash and set password"""
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        """Verify password"""
        return check_password_hash(self.password_hash, password)
    
    def has_role(self, role_name):
        """Check if user has specific role"""
        return any(role.name == role_name for role in self.roles)
    
    @property
    def full_name(self):
        """Return full name"""
        return f"{self.first_name} {self.last_name}"
    
    def to_dict(self):
        """Serialize to dictionary for API responses"""
        return {
            'id': self.id,
            'username': self.username,
            'email': self.email,
            'full_name': self.full_name,
            'is_active': self.is_active,
            'created_at': self.created_at.isoformat()
        }
    
    def __repr__(self):
        return f'<User {self.username}>'


class Role(db.Model):
    """Role model for role-based access control"""
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)
    description = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<Role {self.name}>'


class VaultEntry(db.Model):
    """Knowledge Vault Entry model"""
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False, index=True)
    content = db.Column(db.Text, nullable=False)
    category = db.Column(db.String(50), index=True)
    tags = db.Column(db.Text)  # JSON string for tags
    is_public = db.Column(db.Boolean, default=True)
    view_count = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Foreign Key
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    
    def to_dict(self):
        """Serialize to dictionary for API responses"""
        return {
            'id': self.id,
            'title': self.title,
            'content': self.content,
            'category': self.category,
            'tags': self.tags,
            'is_public': self.is_public,
            'view_count': self.view_count,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat(),
            'author': self.author.username
        }
    
    def __repr__(self):
        return f'<VaultEntry {self.title}>'


class APIKey(db.Model):
    """API Key model for API authentication"""
    id = db.Column(db.Integer, primary_key=True)
    key_hash = db.Column(db.String(255), unique=True, nullable=False)
    name = db.Column(db.String(100), nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_used = db.Column(db.DateTime)
    
    # Foreign Key
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    
    def __repr__(self):
        return f'<APIKey {self.name}>'
EOF

# Create blueprint __init__.py files
echo "📄 Creating blueprint initialization files..."

# Knowledge Vault Blueprint
cat > app/knowledge_vault/__init__.py << 'EOF'
"""
Knowledge Vault Blueprint - CRUD Operations
Demonstrates Flask blueprint organization and CRUD patterns
"""
from flask import Blueprint

bp = Blueprint('knowledge_vault', __name__, 
               template_folder='templates',
               static_folder='static',
               static_url_path='/vault/static')

from app.knowledge_vault import routes
EOF

# API Hub Blueprint
cat > app/api_hub/__init__.py << 'EOF'
"""
API Hub Blueprint - REST and GraphQL APIs
Demonstrates Flask API development with multiple paradigms
"""
from flask import Blueprint

bp = Blueprint('api_hub', __name__, 
               template_folder='templates',
               static_folder='static')

from app.api_hub import rest_routes, graphql_routes
EOF

# Dashboard Blueprint
cat > app/dashboard/__init__.py << 'EOF'
"""
Dashboard Blueprint - Real-time WebSocket Dashboard
Demonstrates Flask-SocketIO integration and real-time features
"""
from flask import Blueprint

bp = Blueprint('dashboard', __name__, 
               template_folder='templates',
               static_folder='static',
               static_url_path='/dashboard/static')

from app.dashboard import routes, sockets
EOF

# Auth Blueprint
cat > app/auth/__init__.py << 'EOF'
"""
Authentication Blueprint - User Management and Security
Demonstrates Flask-Login, JWT, and security best practices
"""
from flask import Blueprint

bp = Blueprint('auth', __name__, 
               template_folder='templates',
               static_folder='static')

from app.auth import routes
EOF

# Error handling blueprint
cat > app/errors/__init__.py << 'EOF'
"""
Error Handling Blueprint
Demonstrates Flask error handling and custom error pages
"""
from flask import Blueprint

bp = Blueprint('errors', __name__, 
               template_folder='templates')

from app.errors import handlers
EOF

# CLI commands blueprint
mkdir -p app/cli
cat > app/cli/__init__.py << 'EOF'
"""
Custom CLI Commands
Demonstrates Flask CLI extensibility
"""
EOF

# Create basic route files
echo "📄 Creating basic route files..."

# Knowledge Vault routes
cat > app/knowledge_vault/routes.py << 'EOF'
"""
Knowledge Vault Routes - CRUD Operations
Demonstrates Flask routing, forms, templates, and database operations
"""
from flask import render_template, request, flash, redirect, url_for, jsonify
from flask_login import login_required, current_user
from app.knowledge_vault import bp
from app.models import VaultEntry
from app.extensions import db


@bp.route('/')
@bp.route('/index')
def index():
    """List all vault entries with pagination"""
    page = request.args.get('page', 1, type=int)
    entries = VaultEntry.query.filter_by(is_public=True).paginate(
        page=page, per_page=10, error_out=False
    )
    return render_template('vault_index.html', entries=entries)


@bp.route('/entry/<int:id>')
def detail(id):
    """Show single vault entry"""
    entry = VaultEntry.query.get_or_404(id)
    entry.view_count += 1
    db.session.commit()
    return render_template('vault_detail.html', entry=entry)


@bp.route('/create', methods=['GET', 'POST'])
@login_required
def create():
    """Create new vault entry"""
    if request.method == 'POST':
        entry = VaultEntry(
            title=request.form['title'],
            content=request.form['content'],
            category=request.form['category'],
            user_id=current_user.id
        )
        db.session.add(entry)
        db.session.commit()
        flash('Entry created successfully!', 'success')
        return redirect(url_for('knowledge_vault.detail', id=entry.id))
    
    return render_template('vault_create.html')


@bp.route('/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def edit(id):
    """Edit existing vault entry"""
    entry = VaultEntry.query.get_or_404(id)
    
    if entry.user_id != current_user.id:
        flash('You can only edit your own entries.', 'error')
        return redirect(url_for('knowledge_vault.detail', id=entry.id))
    
    if request.method == 'POST':
        entry.title = request.form['title']
        entry.content = request.form['content']
        entry.category = request.form['category']
        db.session.commit()
        flash('Entry updated successfully!', 'success')
        return redirect(url_for('knowledge_vault.detail', id=entry.id))
    
    return render_template('vault_edit.html', entry=entry)


@bp.route('/delete/<int:id>', methods=['POST'])
@login_required
def delete(id):
    """Delete vault entry"""
    entry = VaultEntry.query.get_or_404(id)
    
    if entry.user_id != current_user.id:
        return jsonify({'error': 'Unauthorized'}), 403
    
    db.session.delete(entry)
    db.session.commit()
    flash('Entry deleted successfully!', 'success')
    return redirect(url_for('knowledge_vault.index'))
EOF

# Auth routes
cat > app/auth/routes.py << 'EOF'
"""
Authentication Routes
Demonstrates Flask-Login, session management, and security
"""
from flask import render_template, request, flash, redirect, url_for
from flask_login import login_user, logout_user, login_required, current_user
from app.auth import bp
from app.models import User
from app.extensions import db


@bp.route('/login', methods=['GET', 'POST'])
def login():
    """User login"""
    if current_user.is_authenticated:
        return redirect(url_for('knowledge_vault.index'))
    
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()
        
        if user and user.check_password(password):
            login_user(user, remember=request.form.get('remember', False))
            return redirect(url_for('knowledge_vault.index'))
        else:
            flash('Invalid username or password', 'error')
    
    return render_template('login.html')


@bp.route('/register', methods=['GET', 'POST'])
def register():
    """User registration"""
    if current_user.is_authenticated:
        return redirect(url_for('knowledge_vault.index'))
    
    if request.method == 'POST':
        user = User(
            username=request.form['username'],
            email=request.form['email'],
            first_name=request.form['first_name'],
            last_name=request.form['last_name']
        )
        user.set_password(request.form['password'])
        db.session.add(user)
        db.session.commit()
        
        flash('Registration successful!', 'success')
        return redirect(url_for('auth.login'))
    
    return render_template('register.html')


@bp.route('/logout')
@login_required
def logout():
    """User logout"""
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('auth.login'))


@bp.route('/profile')
@login_required
def profile():
    """User profile"""
    return render_template('profile.html')
EOF

# API routes placeholder
cat > app/api_hub/rest_routes.py << 'EOF'
"""
REST API Routes
Demonstrates Flask RESTful API development with proper HTTP methods
"""
from flask import jsonify, request
from app.api_hub import bp
from app.models import VaultEntry, User
from app.extensions import db


@bp.route('/entries', methods=['GET'])
def get_entries():
    """GET /api/entries - List all entries"""
    page = request.args.get('page', 1, type=int)
    entries = VaultEntry.query.filter_by(is_public=True).paginate(
        page=page, per_page=20, error_out=False
    )
    
    return jsonify({
        'entries': [entry.to_dict() for entry in entries.items],
        'total': entries.total,
        'pages': entries.pages,
        'current_page': page
    })


@bp.route('/entries/<int:id>', methods=['GET'])
def get_entry(id):
    """GET /api/entries/<id> - Get single entry"""
    entry = VaultEntry.query.get_or_404(id)
    return jsonify(entry.to_dict())


@bp.route('/entries', methods=['POST'])
def create_entry():
    """POST /api/entries - Create new entry"""
    data = request.get_json()
    
    entry = VaultEntry(
        title=data['title'],
        content=data['content'],
        category=data.get('category'),
        user_id=1  # TODO: Get from JWT token
    )
    
    db.session.add(entry)
    db.session.commit()
    
    return jsonify(entry.to_dict()), 201


@bp.route('/users', methods=['GET'])
def get_users():
    """GET /api/users - List all users"""
    users = User.query.all()
    return jsonify([user.to_dict() for user in users])
EOF

# Create basic templates
echo "📄 Creating base templates..."

# Base template
cat > app/templates/base.html << 'EOF'
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{% block title %}FlaskVerseHub - Master Flask Development{% endblock %}</title>
    
    <!-- Bootstrap CSS -->
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
    
    <!-- Custom CSS -->
    <link rel="stylesheet" href="{{ url_for('static', filename='css/base.css') }}">
    {% block styles %}{% endblock %}
</head>
<body>
    {% include 'shared_components/navbar.html' %}
    
    <main class="container-fluid">
        {% include 'shared_components/flash_messages.html' %}
        
        {% block content %}{% endblock %}
    </main>
    
    {% include 'shared_components/footer.html' %}
    
    <!-- Bootstrap JS -->
    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/js/bootstrap.bundle.min.js"></script>
    
    <!-- Custom JS -->
    <script src="{{ url_for('static', filename='js/main.js') }}"></script>
    {% block scripts %}{% endblock %}
</body>
</html>
EOF

# Create shared components
cat > app/templates/shared_components/navbar.html << 'EOF'
<nav class="navbar navbar-expand-lg navbar-dark bg-primary">
    <div class="container">
        <a class="navbar-brand" href="{{ url_for('knowledge_vault.index') }}">
            🔬 FlaskVerseHub
        </a>
        
        <button class="navbar-toggler" type="button" data-bs-toggle="collapse" data-bs-target="#navbarNav">
            <span class="navbar-toggler-icon"></span>
        </button>
        
        <div class="collapse navbar-collapse" id="navbarNav">
            <ul class="navbar-nav me-auto">
                <li class="nav-item">
                    <a class="nav-link" href="{{ url_for('knowledge_vault.index') }}">Knowledge Vault</a>
                </li>
                <li class="nav-item">
                    <a class="nav-link" href="{{ url_for('dashboard.index') }}">Dashboard</a>
                </li>
                <li class="nav-item">
                    <a class="nav-link" href="/api/docs">API Docs</a>
                </li>
            </ul>
            
            <ul class="navbar-nav">
                {% if current_user.is_authenticated %}
                    <li class="nav-item dropdown">
                        <a class="nav-link dropdown-toggle" href="#" id="navbarDropdown" role="button" data-bs-toggle="dropdown">
                            {{ current_user.username }}
                        </a>
                        <ul class="dropdown-menu">
                            <li><a class="dropdown-item" href="{{ url_for('auth.profile') }}">Profile</a></li>
                            <li><hr class="dropdown-divider"></li>
                            <li><a class="dropdown-item" href="{{ url_for('auth.logout') }}">Logout</a></li>
                        </ul>
                    </li>
                {% else %}
                    <li class="nav-item">
                        <a class="nav-link" href="{{ url_for('auth.login') }}">Login</a>
                    </li>
                    <li class="nav-item">
                        <a class="nav-link" href="{{ url_for('auth.register') }}">Register</a>
                    </li>
                {% endif %}
            </ul>
        </div>
    </div>
</nav>
EOF

# Flash messages component
cat > app/templates/shared_components/flash_messages.html << 'EOF'
{% with messages = get_flashed_messages(with_categories=true) %}
    {% if messages %}
        <div class="container mt-3">
            {% for category, message in messages %}
                <div class="alert alert-{{ 'danger' if category == 'error' else category }} alert-dismissible fade show" role="alert">
                    {{ message }}
                    <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
                </div>
            {% endfor %}
        </div>
    {% endif %}
{% endwith %}
EOF

# Create requirements files
echo "📄 Creating requirements files..."

cat > requirements/base.txt << 'EOF'
# Core Flask
Flask==2.3.3
Werkzeug==2.3.7

# Database
Flask-SQLAlchemy==3.0.5
Flask-Migrate==4.0.5

# Authentication
Flask-Login==0.6.3
PyJWT==2.8.0

# Forms
Flask-WTF==1.1.1
WTForms==3.0.1

# Email
Flask-Mail==0.9.1

# Caching
Flask-Caching==2.1.0
redis==4.6.0

# WebSockets
Flask-SocketIO==5.3.6

# Security
Flask-Limiter==3.5.0

# API Development
Flask-RESTful==0.3.10
marshmallow==3.20.1
flask-marshmallow==0.15.0

# GraphQL
graphene==3.3
flask-graphql==2.0.1

# Environment
python-dotenv==1.0.0

# Date/Time
python-dateutil==2.8.2

# Utilities
click==8.1.7
EOF

cat > requirements/dev.txt << 'EOF'
-r base.txt

# Development tools
Flask-DebugToolbar==0.13.1

# Testing
pytest==7.4.2
pytest-flask==1.2.0
pytest-cov==4.1.0

# Code quality
flake8==6.1.0
black==23.9.1
isort==5.12.0

# Documentation
Sphinx==7.2.6
EOF

cat > requirements/prod.txt << 'EOF'
-r base.txt

# Production server
gunicorn==21.2.0

# Monitoring
sentry-sdk[flask]==1.32.0

# Production database
psycopg2-binary==2.9.7
EOF

cat > requirements/test.txt << 'EOF'
-r base.txt

# Testing
pytest==7.4.2
pytest-flask==1.2.0
pytest-cov==4.1.0
factory-boy==3.3.0
EOF

# Create main entry points
echo "📄 Creating entry point files..."

cat > manage.py << 'EOF'
#!/usr/bin/env python
"""
Flask CLI Management Script
Entry point for running the Flask application
"""
import os
from app import create_app
from app.extensions import db
from app.models import User, Role, VaultEntry

# Create app instance
app = create_app()


@app.shell_context_processor
def make_shell_context():
    """Add variables to shell context for flask shell"""
    return {
        'db': db,
        'User': User,
        'Role': Role, 
        'VaultEntry': VaultEntry
    }


if __name__ == '__main__':
    app.run(debug=True)
EOF

cat > wsgi.py << 'EOF'
"""
WSGI Entry Point for Production Deployment
"""
from app import create_app

app = create_app()

if __name__ == "__main__":
    app.run()
EOF

# Create environment file template
cat > .env.example << 'EOF'
# Flask Configuration
FLASK_APP=manage.py
FLASK_ENV=development
SECRET_KEY=your-secret-key-here

# Database
DATABASE_URL=sqlite:///flaskversehub.db

# Redis (for caching and rate limiting)
REDIS_URL=redis://localhost:6379/0

# Email Configuration
MAIL_SERVER=smtp.gmail.com
MAIL_PORT=587
MAIL_USE_TLS=1
MAIL_USERNAME=your-email@example.com
MAIL_PASSWORD=your-app-password
MAIL_DEFAULT_SENDER=your-email@example.com

# JWT Configuration
JWT_SECRET_KEY=your-jwt-secret-key
EOF

# Create Docker files
echo "📄 Creating Docker configuration..."

cat > docker/Dockerfile << 'EOF'
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements/prod.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create non-root user
RUN adduser --disabled-password --gecos '' appuser
RUN chown -R appuser:appuser /app
USER appuser

# Expose port
EXPOSE 5000

# Run application
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "4", "wsgi:app"]
EOF

cat > docker/docker-compose.yml << 'EOF'
version: '3.8'

services:
  web:
    build:
      context: ..
      dockerfile: docker/Dockerfile
    ports:
      - "5000:5000"
    environment:
      - FLASK_ENV=production
      - DATABASE_URL=postgresql://user:password@db:5432/flaskversehub
      - REDIS_URL=redis://redis:6379/0
    depends_on:
      - db
      - redis
    volumes:
      - ..:/app

  db:
    image: postgres:15
    environment:
      - POSTGRES_DB=flaskversehub
      - POSTGRES_USER=user
      - POSTGRES_PASSWORD=password
    volumes:
      - postgres_data:/var/lib/postgresql/data
    ports:
      - "5432:5432"

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"

volumes:
  postgres_data:
EOF

# Create GitHub Actions
echo "📄 Creating GitHub Actions..."

mkdir -p .github/workflows
cat > .github/workflows/ci.yml << 'EOF'
name: CI

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    
    services:
      postgres:
        image: postgres:15
        env:
          POSTGRES_PASSWORD: postgres
          POSTGRES_DB: test_db
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
        ports:
          - 5432:5432
      
      redis:
        image: redis:7-alpine
        options: >-
          --health-cmd "redis-cli ping"
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
        ports:
          - 6379:6379

    steps:
    - uses: actions/checkout@v3
    
    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.11'
    
    - name: Install dependencies
      run: |
        python -m pip install --upgrade pip
        pip install -r requirements/test.txt
    
    - name: Run tests
      env:
        DATABASE_URL: postgresql://postgres:postgres@localhost:5432/test_db
        REDIS_URL: redis://localhost:6379/0
      run: |
        pytest --cov=app --cov-report=xml
    
    - name: Upload coverage to Codecov
      uses: codecov/codecov-action@v3
EOF

# Create basic test files
echo "📄 Creating test files..."

cat > tests/conftest.py << 'EOF'
"""
Pytest configuration and fixtures
"""
import pytest
from app import create_app
from app.extensions import db
from app.models import User, Role, VaultEntry
from app.config import TestingConfig


@pytest.fixture
def app():
    """Create application for testing"""
    app = create_app(TestingConfig)
    
    with app.app_context():
        db.create_all()
        yield app
        db.drop_all()


@pytest.fixture
def client(app):
    """Test client"""
    return app.test_client()


@pytest.fixture
def runner(app):
    """Test CLI runner"""
    return app.test_cli_runner()


@pytest.fixture
def user(app):
    """Create test user"""
    user = User(
        username='testuser',
        email='test@example.com',
        first_name='Test',
        last_name='User'
    )
    user.set_password('password')
    db.session.add(user)
    db.session.commit()
    return user
EOF

# Create pytest configuration
cat > pytest.ini << 'EOF'
[tool:pytest]
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*
addopts = -v --tb=short
EOF

# Create documentation files
echo "📄 Creating documentation..."

cat > docs/README.md << 'EOF'
# FlaskVerseHub Documentation

Welcome to FlaskVerseHub - a comprehensive Flask mastery project that demonstrates every major Flask concept through practical implementation.

## Getting Started

1. Clone the repository
2. Copy `.env.example` to `.env` and configure your environment
3. Install dependencies: `pip install -r requirements/dev.txt`
4. Initialize database: `flask db upgrade`
5. Run the application: `python manage.py`

## Project Structure

This project is organized into several blueprints, each demonstrating different Flask concepts:

- **Knowledge Vault**: CRUD operations, forms, templates
- **API Hub**: REST and GraphQL APIs
- **Dashboard**: Real-time features with WebSockets
- **Auth**: Authentication and authorization

## Flask Concepts Covered

- App Factory Pattern
- Blueprints and Application Structure
- SQLAlchemy ORM and Database Migrations
- Flask-Login and JWT Authentication
- WTForms and Form Handling
- Template Inheritance and Jinja2
- RESTful API Development
- GraphQL Integration
- WebSocket Real-time Features
- Caching and Performance
- Security Best Practices
- Testing and CI/CD
- Docker Deployment

## Contributing

Please read the contributing guidelines before submitting pull requests.
EOF

# Create .gitignore
cat > .gitignore << 'EOF'
# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
build/
develop-eggs/
dist/
downloads/
eggs/
.eggs/
lib/
lib64/
parts/
sdist/
var/
wheels/
pip-wheel-metadata/
share/python-wheels/
*.egg-info/
.installed.cfg
*.egg
MANIFEST

# Flask
instance/
.webassets-cache

# Environment variables
.env
.venv
env/
venv/
ENV/
env.bak/
venv.bak/

# Database
*.db
*.sqlite3

# IDE
.vscode/
.idea/
*.swp
*.swo
*~

# OS
.DS_Store
.DS_Store?
._*
.Spotlight-V100
.Trashes
ehthumbs.db
Thumbs.db

# Logs
logs/
*.log

# Testing
.coverage
htmlcov/
.pytest_cache/

# Docker
.dockerignore

# Node.js (if using for frontend tools)
node_modules/
npm-debug.log*
yarn-debug.log*
yarn-error.log*
EOF

# Create README
cat > README.md << 'EOF'
# 🔬 FlaskVerseHub

**Master Every Flask Concept Through One Unified Project**

FlaskVerseHub is a comprehensive, portfolio-grade Flask application that demonstrates complete mastery of Flask development from fundamentals to advanced concepts.

## ✨ Features

- **🗃️ Knowledge Vault**: Full CRUD operations with forms and validation
- **🔌 API Hub**: REST and GraphQL APIs with documentation
- **📊 Real-time Dashboard**: WebSocket-powered live updates
- **🔐 Authentication**: Complete user management with JWT support
- **🛡️ Security**: CSRF protection, rate limiting, input sanitization
- **🧪 Testing**: Comprehensive test suite with CI/CD
- **🐳 Docker Ready**: Production deployment configuration

## 🚀 Quick Start

1. **Clone and setup**:
   ```bash
   git clone <repository-url>
   cd FlaskVerseHub
   cp .env.example .env
   ```

2. **Install dependencies**:
   ```bash
   pip install -r requirements/dev.txt
   ```

3. **Initialize database**:
   ```bash
   flask db upgrade
   ```

4. **Run the application**:
   ```bash
   python manage.py
   ```

5. **Visit**: http://localhost:5000

## 📚 Flask Concepts Demonstrated

### Core Flask
- ✅ App Factory Pattern
- ✅ Blueprint Organization
- ✅ Routing and View Functions
- ✅ Template Inheritance
- ✅ Static File Handling

### Database & Models
- ✅ SQLAlchemy ORM
- ✅ Database Migrations
- ✅ Model Relationships
- ✅ Query Optimization

### Security & Authentication
- ✅ Flask-Login Sessions
- ✅ JWT Token Authentication
- ✅ Password Hashing
- ✅ CSRF Protection
- ✅ Rate Limiting

### APIs & Serialization
- ✅ RESTful API Design
- ✅ GraphQL Integration
- ✅ Data Serialization
- ✅ API Documentation

### Real-time Features
- ✅ WebSocket Integration
- ✅ Live Notifications
- ✅ Real-time Updates

### Testing & Quality
- ✅ Unit Testing
- ✅ Integration Testing
- ✅ CI/CD Pipeline
- ✅ Code Coverage

### Deployment
- ✅ Docker Configuration
- ✅ Production Settings
- ✅ Environment Management

## 🏗️ Project Structure

```
FlaskVerseHub/
├── app/                    # Main application package
│   ├── knowledge_vault/    # CRUD operations blueprint
│   ├── api_hub/           # REST + GraphQL APIs
│   ├── dashboard/         # Real-time dashboard
│   ├── auth/              # Authentication system
│   └── ...
├── tests/                 # Test suite
├── docker/               # Docker configuration
├── requirements/         # Dependencies by environment
└── docs/                # Documentation
```

## 🧪 Testing

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=app

# Run specific test file
pytest tests/test_models.py
```

## 🐳 Docker Deployment

```bash
# Build and run
cd docker
docker-compose up --build

# Production deployment
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up
```

## 📖 Documentation

- [Architecture Overview](docs/ARCHITECTURE.md)
- [API Reference](docs/API_REFERENCE.md)
- [Deployment Guide](docs/DEPLOYMENT.md)
- [Flask Concepts Covered](docs/FLASK_CONCEPTS.md)

## 🤝 Contributing

This is a learning project, but contributions are welcome! Please read our contributing guidelines before submitting PRs.

## 📄 License

MIT License - see [LICENSE](LICENSE) file for details.

---

**FlaskVerseHub** - *Where Flask mastery begins* 🚀
EOF

# Make manage.py executable
chmod +x manage.py

echo ""
echo "🎉 FlaskVerseHub project structure generated successfully!"
echo ""
echo "📋 Next steps:"
echo "   1. cd $PROJECT_NAME"
echo "   2. python -m venv venv"
echo "   3. source venv/bin/activate  (or 'venv\\Scripts\\activate' on Windows)"
echo "   4. pip install -r requirements/dev.txt"
echo "   5. cp .env.example .env"
echo "   6. flask db init && flask db migrate -m 'Initial migration' && flask db upgrade"
echo "   7. python manage.py"
echo ""
echo "🌟 Your Flask mastery journey begins now!"
echo "📚 Check the generated README.md for detailed instructions"

chmod +x generate_flaskversehub.sh

echo "✅ FlaskVerseHub project generator script created successfully!"
echo ""
echo "🚀 To generate your project structure, run:"
echo "   chmod +x generate_flaskversehub.sh"
echo "   ./generate_flaskversehub.sh"
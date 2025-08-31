# File: FlaskVerseHub/app/models.py

from datetime import datetime, timezone
from flask import current_app
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy.dialects.postgresql import UUID
import uuid
import secrets
from app.extensions import db


# Association Tables for Many-to-Many relationships
knowledge_categories = db.Table(
    'knowledge_categories',
    db.Column('knowledge_id', db.Integer, db.ForeignKey('knowledge_item.id'), primary_key=True),
    db.Column('category_id', db.Integer, db.ForeignKey('category.id'), primary_key=True),
    db.Column('created_at', db.DateTime, default=lambda: datetime.now(timezone.utc))
)

user_roles = db.Table(
    'user_roles',
    db.Column('user_id', db.Integer, db.ForeignKey('user.id'), primary_key=True),
    db.Column('role_id', db.Integer, db.ForeignKey('role.id'), primary_key=True),
    db.Column('assigned_at', db.DateTime, default=lambda: datetime.now(timezone.utc))
)


class TimestampMixin:
    """Mixin to add timestamp fields to models."""
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), 
                          onupdate=lambda: datetime.now(timezone.utc), nullable=False)


class User(UserMixin, db.Model, TimestampMixin):
    """User model for authentication and user management."""
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    first_name = db.Column(db.String(50), nullable=False)
    last_name = db.Column(db.String(50), nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    
    # Profile fields
    bio = db.Column(db.Text)
    avatar_url = db.Column(db.String(255))
    phone = db.Column(db.String(20))
    location = db.Column(db.String(100))
    website = db.Column(db.String(255))
    
    # Account status
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    is_admin = db.Column(db.Boolean, default=False, nullable=False)
    email_verified = db.Column(db.Boolean, default=False, nullable=False)
    
    # Authentication tracking
    last_login = db.Column(db.DateTime)
    login_count = db.Column(db.Integer, default=0)
    failed_login_attempts = db.Column(db.Integer, default=0)
    locked_until = db.Column(db.DateTime)
    
    # Password reset
    reset_token = db.Column(db.String(255))
    reset_token_expires = db.Column(db.DateTime)
    
    # Email verification
    verification_token = db.Column(db.String(255))
    verification_token_expires = db.Column(db.DateTime)
    
    # Preferences
    timezone = db.Column(db.String(50), default='UTC')
    language = db.Column(db.String(10), default='en')
    theme = db.Column(db.String(20), default='light')
    
    # Relationships
    knowledge_items = db.relationship('KnowledgeItem', backref='author', lazy='dynamic')
    api_keys = db.relationship('ApiKey', backref='owner', lazy='dynamic')
    activities = db.relationship('Activity', backref='user', lazy='dynamic')
    roles = db.relationship('Role', secondary=user_roles, backref='users')
    
    def set_password(self, password):
        """Set password hash."""
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        """Check password against hash."""
        return check_password_hash(self.password_hash, password)
    
    def generate_reset_token(self):
        """Generate password reset token."""
        self.reset_token = secrets.token_urlsafe(32)
        self.reset_token_expires = datetime.now(timezone.utc) + current_app.config.get(
            'PASSWORD_RESET_EXPIRES', 3600
        )
        db.session.commit()
        return self.reset_token
    
    def verify_reset_token(self, token):
        """Verify password reset token."""
        return (self.reset_token == token and 
                self.reset_token_expires > datetime.now(timezone.utc))
    
    def generate_verification_token(self):
        """Generate email verification token."""
        self.verification_token = secrets.token_urlsafe(32)
        self.verification_token_expires = datetime.now(timezone.utc) + current_app.config.get(
            'EMAIL_VERIFICATION_EXPIRES', 86400
        )
        db.session.commit()
        return self.verification_token
    
    @property
    def full_name(self):
        """Get user's full name."""
        return f"{self.first_name} {self.last_name}"
    
    @property
    def is_locked(self):
        """Check if account is locked."""
        return self.locked_until and self.locked_until > datetime.now(timezone.utc)
    
    def to_dict(self):
        """Convert user to dictionary."""
        return {
            'id': self.id,
            'username': self.username,
            'email': self.email,
            'full_name': self.full_name,
            'is_active': self.is_active,
            'is_admin': self.is_admin,
            'created_at': self.created_at.isoformat(),
            'last_login': self.last_login.isoformat() if self.last_login else None
        }
    
    def __repr__(self):
        return f'<User {self.username}>'


class Role(db.Model, TimestampMixin):
    """Role model for role-based access control."""
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(64), unique=True, nullable=False)
    description = db.Column(db.String(255))
    permissions = db.Column(db.JSON)
    is_default = db.Column(db.Boolean, default=False)
    
    def __repr__(self):
        return f'<Role {self.name}>'


class Category(db.Model, TimestampMixin):
    """Category model for organizing knowledge items."""
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)
    description = db.Column(db.Text)
    color = db.Column(db.String(7), default='#007bff')  # Hex color code
    icon = db.Column(db.String(50), default='fa-folder')
    slug = db.Column(db.String(100), nullable=False, unique=True, index=True)
    
    # Hierarchy support
    parent_id = db.Column(db.Integer, db.ForeignKey('category.id'))
    parent = db.relationship('Category', remote_side=[id], backref='children')
    
    # Stats
    item_count = db.Column(db.Integer, default=0)
    
    def __repr__(self):
        return f'<Category {self.name}>'


class KnowledgeItem(db.Model, TimestampMixin):
    """Knowledge item model for CRUD operations."""
    
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), nullable=False, index=True)
    content = db.Column(db.Text, nullable=False)
    summary = db.Column(db.String(500))
    
    # Metadata
    slug = db.Column(db.String(255), nullable=False, unique=True, index=True)
    status = db.Column(db.String(20), default='draft', nullable=False)  # draft, published, archived
    priority = db.Column(db.String(20), default='normal')  # low, normal, high, critical
    difficulty = db.Column(db.String(20), default='beginner')  # beginner, intermediate, advanced, expert
    
    # Content metadata
    content_type = db.Column(db.String(50), default='markdown')
    word_count = db.Column(db.Integer, default=0)
    reading_time = db.Column(db.Integer, default=0)  # in minutes
    
    # SEO
    meta_description = db.Column(db.String(160))
    meta_keywords = db.Column(db.String(255))
    
    # Versioning
    version = db.Column(db.Integer, default=1)
    
    # User relationships
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    updated_by = db.Column(db.Integer, db.ForeignKey('user.id'))
    
    # Stats
    view_count = db.Column(db.Integer, default=0)
    like_count = db.Column(db.Integer, default=0)
    share_count = db.Column(db.Integer, default=0)
    
    # File attachments
    has_attachments = db.Column(db.Boolean, default=False)
    attachment_count = db.Column(db.Integer, default=0)
    
    # Publishing
    published_at = db.Column(db.DateTime)
    featured = db.Column(db.Boolean, default=False)
    
    # Relationships
    categories = db.relationship('Category', secondary=knowledge_categories, backref='knowledge_items')
    attachments = db.relationship('Attachment', backref='knowledge_item', lazy='dynamic')
    
    def __repr__(self):
        return f'<KnowledgeItem {self.title}>'
    
    def to_dict(self):
        """Convert knowledge item to dictionary."""
        return {
            'id': self.id,
            'title': self.title,
            'content': self.content,
            'summary': self.summary,
            'slug': self.slug,
            'status': self.status,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat(),
            'author': self.author.username,
            'view_count': self.view_count,
            'categories': [cat.name for cat in self.categories]
        }


class Attachment(db.Model, TimestampMixin):
    """File attachment model for knowledge items."""
    
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(255), nullable=False)
    original_filename = db.Column(db.String(255), nullable=False)
    file_path = db.Column(db.String(500), nullable=False)
    file_size = db.Column(db.Integer, nullable=False)
    content_type = db.Column(db.String(100), nullable=False)
    checksum = db.Column(db.String(64))
    
    # Metadata
    description = db.Column(db.Text)
    is_public = db.Column(db.Boolean, default=True)
    download_count = db.Column(db.Integer, default=0)
    
    # Relationships
    knowledge_item_id = db.Column(db.Integer, db.ForeignKey('knowledge_item.id'), nullable=False)
    uploaded_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    uploader = db.relationship('User', backref='attachments')
    
    def __repr__(self):
        return f'<Attachment {self.original_filename}>'


class ApiKey(db.Model, TimestampMixin):
    """API key model for API authentication."""
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    key_hash = db.Column(db.String(255), nullable=False, unique=True)
    prefix = db.Column(db.String(10), nullable=False)  # First few chars for identification
    
    # Permissions
    scopes = db.Column(db.JSON, default=list)  # List of allowed scopes
    rate_limit = db.Column(db.Integer, default=100)  # Requests per hour
    
    # Status
    is_active = db.Column(db.Boolean, default=True)
    expires_at = db.Column(db.DateTime)
    
    # Usage tracking
    last_used = db.Column(db.DateTime)
    usage_count = db.Column(db.Integer, default=0)
    
    # Relationships
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    
    @staticmethod
    def generate_key():
        """Generate a new API key."""
        return secrets.token_urlsafe(32)
    
    def set_key(self, key):
        """Set API key hash."""
        self.key_hash = generate_password_hash(key)
        self.prefix = key[:8]
    
    def check_key(self, key):
        """Check API key against hash."""
        return check_password_hash(self.key_hash, key)
    
    @property
    def is_expired(self):
        """Check if API key is expired."""
        return self.expires_at and self.expires_at < datetime.now(timezone.utc)
    
    def __repr__(self):
        return f'<ApiKey {self.name}>'


class Activity(db.Model, TimestampMixin):
    """Activity log model for tracking user actions."""
    
    id = db.Column(db.Integer, primary_key=True)
    action = db.Column(db.String(50), nullable=False)  # create, read, update, delete, login, logout
    resource_type = db.Column(db.String(50))  # knowledge_item, user, api_key, etc.
    resource_id = db.Column(db.Integer)
    description = db.Column(db.String(255))
    
    # Request metadata
    ip_address = db.Column(db.String(45))
    user_agent = db.Column(db.String(255))
    endpoint = db.Column(db.String(100))
    method = db.Column(db.String(10))
    status_code = db.Column(db.Integer)
    
    # Additional data
    metadata = db.Column(db.JSON)
    
    # Relationships
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    
    def __repr__(self):
        return f'<Activity {self.action} by {self.user.username if self.user else "Anonymous"}>'
    
    def to_dict(self):
        """Convert activity to dictionary."""
        return {
            'id': self.id,
            'action': self.action,
            'resource_type': self.resource_type,
            'resource_id': self.resource_id,
            'description': self.description,
            'created_at': self.created_at.isoformat(),
            'user': self.user.username if self.user else None,
            'ip_address': self.ip_address
        }


class Setting(db.Model, TimestampMixin):
    """Application settings model."""
    
    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(100), nullable=False, unique=True)
    value = db.Column(db.Text)
    value_type = db.Column(db.String(20), default='string')  # string, int, bool, json
    description = db.Column(db.String(255))
    category = db.Column(db.String(50), default='general')
    is_public = db.Column(db.Boolean, default=False)  # Can be read by non-admin users
    
    @classmethod
    def get_value(cls, key, default=None):
        """Get setting value with type conversion."""
        setting = cls.query.filter_by(key=key).first()
        if not setting:
            return default
        
        value = setting.value
        if setting.value_type == 'int':
            return int(value) if value else default
        elif setting.value_type == 'bool':
            return value.lower() in ('true', '1', 'yes') if value else default
        elif setting.value_type == 'json':
            import json
            return json.loads(value) if value else default
        else:
            return value or default
    
    @classmethod
    def set_value(cls, key, value, value_type='string'):
        """Set setting value."""
        setting = cls.query.filter_by(key=key).first()
        if not setting:
            setting = cls(key=key)
            db.session.add(setting)
        
        if value_type == 'json':
            import json
            value = json.dumps(value)
        else:
            value = str(value)
        
        setting.value = value
        setting.value_type = value_type
        db.session.commit()
        return setting
    
    def __repr__(self):
        return f'<Setting {self.key}>'


# Event listeners for automated tasks
@db.event.listens_for(KnowledgeItem, 'before_insert')
@db.event.listens_for(KnowledgeItem, 'before_update')
def update_knowledge_item_stats(mapper, connection, target):
    """Update knowledge item stats before save."""
    if target.content:
        # Calculate word count
        import re
        words = re.findall(r'\w+', target.content)
        target.word_count = len(words)
        
        # Estimate reading time (average 200 words per minute)
        target.reading_time = max(1, target.word_count // 200)
    
    # Generate slug if not provided
    if not target.slug and target.title:
        import re
        slug = re.sub(r'[^\w\s-]', '', target.title.lower())
        target.slug = re.sub(r'[-\s]+', '-', slug)


@db.event.listens_for(User, 'after_insert')
def assign_default_role(mapper, connection, target):
    """Assign default role to new users."""
    default_role = Role.query.filter_by(is_default=True).first()
    if default_role:
        target.roles.append(default_role)
# File: app/auth/decorators.py
# 🔐 Auth Decorators (login_required, role_required)

from functools import wraps
from flask import abort, request, jsonify, current_app
from flask_login import current_user
import jwt
from datetime import datetime


def login_required(f):
    """Decorator to require authentication."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            if request.is_json or request.path.startswith('/api/'):
                return jsonify({'error': 'Authentication required'}), 401
            abort(401)
        return f(*args, **kwargs)
    return decorated_function


def role_required(*roles):
    """Decorator to require specific roles."""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                if request.is_json or request.path.startswith('/api/'):
                    return jsonify({'error': 'Authentication required'}), 401
                abort(401)
            
            # Check if user has any of the required roles
            user_roles = getattr(current_user, 'roles', [])
            if isinstance(user_roles, str):
                user_roles = [user_roles]
            
            # Admin role bypasses all other role requirements
            if current_user.is_admin or 'admin' in user_roles:
                return f(*args, **kwargs)
            
            # Check specific roles
            has_required_role = False
            for role in roles:
                if role in user_roles or (role == 'admin' and current_user.is_admin):
                    has_required_role = True
                    break
            
            if not has_required_role:
                if request.is_json or request.path.startswith('/api/'):
                    return jsonify({'error': 'Insufficient permissions'}), 403
                abort(403)
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator


def admin_required(f):
    """Decorator to require admin role."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            if request.is_json or request.path.startswith('/api/'):
                return jsonify({'error': 'Authentication required'}), 401
            abort(401)
        
        if not current_user.is_admin:
            if request.is_json or request.path.startswith('/api/'):
                return jsonify({'error': 'Admin access required'}), 403
            abort(403)
        
        return f(*args, **kwargs)
    return decorated_function


def api_key_required(f):
    """Decorator to require API key authentication."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        api_key = request.headers.get('X-API-Key')
        
        if not api_key:
            return jsonify({'error': 'API key required'}), 401
        
        # Validate API key (implement your API key validation logic)
        if not validate_api_key(api_key):
            return jsonify({'error': 'Invalid API key'}), 401
        
        return f(*args, **kwargs)
    return decorated_function


def jwt_required(optional=False):
    """Decorator to require JWT token authentication."""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            token = None
            
            # Get token from Authorization header
            auth_header = request.headers.get('Authorization')
            if auth_header:
                try:
                    token = auth_header.split(' ')[1]  # Bearer <token>
                except IndexError:
                    if not optional:
                        return jsonify({'error': 'Invalid authorization header format'}), 401
            
            if not token and not optional:
                return jsonify({'error': 'JWT token required'}), 401
            
            if token:
                try:
                    payload = jwt.decode(
                        token,
                        current_app.config['SECRET_KEY'],
                        algorithms=['HS256']
                    )
                    
                    # Check token expiration
                    if payload.get('exp', 0) < datetime.utcnow().timestamp():
                        return jsonify({'error': 'Token has expired'}), 401
                    
                    # Add user info to request context
                    request.jwt_user_id = payload.get('user_id')
                    request.jwt_username = payload.get('username')
                    
                except jwt.ExpiredSignatureError:
                    return jsonify({'error': 'Token has expired'}), 401
                except jwt.InvalidTokenError:
                    return jsonify({'error': 'Invalid token'}), 401
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator


def permission_required(permission):
    """Decorator to require specific permission."""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                if request.is_json or request.path.startswith('/api/'):
                    return jsonify({'error': 'Authentication required'}), 401
                abort(401)
            
            # Admin users have all permissions
            if current_user.is_admin:
                return f(*args, **kwargs)
            
            # Check if user has the required permission
            user_permissions = getattr(current_user, 'permissions', [])
            if permission not in user_permissions:
                if request.is_json or request.path.startswith('/api/'):
                    return jsonify({'error': f'Permission "{permission}" required'}), 403
                abort(403)
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator


def owner_required(resource_user_field='user_id'):
    """Decorator to require resource ownership."""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                if request.is_json or request.path.startswith('/api/'):
                    return jsonify({'error': 'Authentication required'}), 401
                abort(401)
            
            # Admin users can access any resource
            if current_user.is_admin:
                return f(*args, **kwargs)
            
            # Get resource ID from URL parameters
            resource_id = kwargs.get('id') or kwargs.get('resource_id')
            
            if not resource_id:
                if request.is_json or request.path.startswith('/api/'):
                    return jsonify({'error': 'Resource ID required'}), 400
                abort(400)
            
            # This would need to be customized based on your resource model
            # For now, we'll assume the resource has a user_id field
            # You might need to pass the model class or implement differently
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator


def rate_limit_required(limit="100/hour", key_func=None):
    """Decorator for rate limiting."""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # This is a placeholder - you'd implement actual rate limiting
            # using Redis or similar storage
            
            if key_func:
                key = key_func()
            else:
                key = f"{current_user.id if current_user.is_authenticated else request.remote_addr}"
            
            # Check rate limit (implement your rate limiting logic)
            if not check_rate_limit(key, limit):
                if request.is_json or request.path.startswith('/api/'):
                    return jsonify({'error': 'Rate limit exceeded'}), 429
                abort(429)
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator


def fresh_login_required(f):
    """Decorator to require fresh login (within last 30 minutes)."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            if request.is_json or request.path.startswith('/api/'):
                return jsonify({'error': 'Authentication required'}), 401
            abort(401)
        
        # Check if login is fresh (within last 30 minutes)
        if not hasattr(current_user, 'last_login') or not current_user.last_login:
            if request.is_json or request.path.startswith('/api/'):
                return jsonify({'error': 'Fresh login required'}), 401
            abort(401)
        
        from datetime import datetime, timedelta
        if datetime.utcnow() - current_user.last_login > timedelta(minutes=30):
            if request.is_json or request.path.startswith('/api/'):
                return jsonify({'error': 'Fresh login required'}), 401
            abort(401)
        
        return f(*args, **kwargs)
    return decorated_function


def verified_email_required(f):
    """Decorator to require verified email."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            if request.is_json or request.path.startswith('/api/'):
                return jsonify({'error': 'Authentication required'}), 401
            abort(401)
        
        if not getattr(current_user, 'email_verified', True):
            if request.is_json or request.path.startswith('/api/'):
                return jsonify({'error': 'Email verification required'}), 403
            abort(403)
        
        return f(*args, **kwargs)
    return decorated_function


def two_factor_required(f):
    """Decorator to require two-factor authentication."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            if request.is_json or request.path.startswith('/api/'):
                return jsonify({'error': 'Authentication required'}), 401
            abort(401)
        
        # Check if user has 2FA enabled and verified
        if getattr(current_user, 'two_factor_enabled', False):
            if not getattr(current_user, 'two_factor_verified', False):
                if request.is_json or request.path.startswith('/api/'):
                    return jsonify({'error': 'Two-factor authentication required'}), 403
                abort(403)
        
        return f(*args, **kwargs)
    return decorated_function


# Helper functions
def validate_api_key(api_key):
    """Validate API key."""
    # Implement your API key validation logic
    # This could check against a database, cache, etc.
    valid_keys = current_app.config.get('VALID_API_KEYS', [])
    return api_key in valid_keys


def check_rate_limit(key, limit):
    """Check if request is within rate limit."""
    # Implement your rate limiting logic
    # This would typically use Redis or similar storage
    # For now, we'll just return True (no limiting)
    return True


def get_user_permissions(user):
    """Get user permissions."""
    # This would typically query a permissions table
    # For now, return basic permissions based on role
    if user.is_admin:
        return ['*']  # All permissions
    
    return ['read', 'write']  # Basic permissions
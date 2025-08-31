# File: app/security/rate_limiting.py
# 🔒 API Rate Limiting

from functools import wraps
from flask import request, jsonify, current_app
from flask_login import current_user
from ..extensions import limiter


def rate_limit(limit_string):
    """Decorator for rate limiting endpoints."""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # Use limiter decorator
            limited_func = limiter.limit(limit_string)(f)
            return limited_func(*args, **kwargs)
        return decorated_function
    return decorator


def get_user_id():
    """Get user ID for rate limiting key."""
    if current_user.is_authenticated:
        return str(current_user.id)
    return request.environ.get('REMOTE_ADDR', 'anonymous')


def api_rate_limit(limit_string):
    """Rate limit for API endpoints."""
    return limiter.limit(limit_string, key_func=get_user_id)


# Rate limiting configurations
RATE_LIMITS = {
    'login': '5/minute',
    'register': '3/minute', 
    'password_reset': '3/hour',
    'api_general': '100/hour',
    'api_create': '20/hour',
    'api_upload': '10/hour'
}
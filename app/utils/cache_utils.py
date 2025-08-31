# File: app/utils/cache_utils.py
# 🔄 Caching Helpers and Decorators

from functools import wraps
from flask import current_app, request
from ..extensions import cache


def cache_key(*args, **kwargs):
    """Generate cache key from arguments."""
    key_parts = []
    
    # Add positional arguments
    for arg in args:
        key_parts.append(str(arg))
    
    # Add keyword arguments
    for k, v in sorted(kwargs.items()):
        key_parts.append(f'{k}:{v}')
    
    return ':'.join(key_parts)


def cached_view(timeout=300, key_prefix='view'):
    """Decorator to cache view results."""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # Generate cache key based on request
            key = f'{key_prefix}:{request.endpoint}:{request.full_path}'
            
            # Try to get from cache
            cached_result = cache.get(key)
            if cached_result is not None:
                return cached_result
            
            # Execute function and cache result
            result = f(*args, **kwargs)
            cache.set(key, result, timeout=timeout)
            
            return result
        return decorated_function
    return decorator


def cached_function(timeout=300, key_func=None):
    """Decorator to cache function results."""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # Generate cache key
            if key_func:
                key = key_func(*args, **kwargs)
            else:
                key = f'{f.__name__}:{cache_key(*args, **kwargs)}'
            
            # Try to get from cache
            cached_result = cache.get(key)
            if cached_result is not None:
                return cached_result
            
            # Execute function and cache result
            result = f(*args, **kwargs)
            cache.set(key, result, timeout=timeout)
            
            return result
        return decorated_function
    return decorator


def invalidate_cache_pattern(pattern):
    """Invalidate cache keys matching pattern."""
    # This would need Redis for pattern matching
    # For simple cache, we can't do pattern matching
    if hasattr(cache.cache, 'delete_many'):
        # For Redis cache
        keys = cache.cache._write_client.keys(pattern)
        if keys:
            cache.cache.delete_many(*keys)
    else:
        # For simple cache, we'd need to clear all
        cache.clear()


def get_or_set_cache(key, func, timeout=300):
    """Get value from cache or set it using function."""
    value = cache.get(key)
    if value is None:
        value = func()
        cache.set(key, value, timeout=timeout)
    return value


# Predefined cache functions
@cached_function(timeout=600)
def get_popular_entries():
    """Get popular entries (cached for 10 minutes)."""
    from ..models import KnowledgeEntry
    return KnowledgeEntry.query.filter_by(
        is_public=True,
        is_featured=True
    ).limit(5).all()


@cached_function(timeout=3600)
def get_category_stats():
    """Get category statistics (cached for 1 hour)."""
    from ..models import KnowledgeEntry, db
    return db.session.query(
        KnowledgeEntry.category,
        db.func.count(KnowledgeEntry.id).label('count')
    ).filter_by(is_public=True).group_by(KnowledgeEntry.category).all()


def clear_user_cache(user_id):
    """Clear all cache for specific user."""
    patterns = [
        f'user:{user_id}:*',
        f'entries:author:{user_id}:*',
    ]
    
    for pattern in patterns:
        invalidate_cache_pattern(pattern)
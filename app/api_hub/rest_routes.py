# File: app/api_hub/rest_routes.py
# 🔌 RESTful API Endpoints

from flask import request, jsonify, current_app, abort
from flask_login import login_required, current_user
from sqlalchemy import desc, asc, or_
from datetime import datetime, timedelta
import jwt

from . import api_hub
from .serializers import (
    KnowledgeEntrySchema, UserSchema, 
    knowledge_entry_schema, knowledge_entries_schema,
    user_schema, users_schema
)
from .pagination import paginate_query
from ..models import KnowledgeEntry, User, db
from ..auth.decorators import api_key_required, role_required
from ..security.rate_limiting import rate_limit
from ..utils.cache_utils import cache


# Authentication endpoints
@api_hub.route('/auth/login', methods=['POST'])
@rate_limit('5/minute')
def api_login():
    """API login endpoint returning JWT token."""
    data = request.get_json()
    
    if not data or not data.get('username') or not data.get('password'):
        return jsonify({'error': 'Username and password required'}), 400
    
    user = User.query.filter_by(username=data['username']).first()
    
    if not user or not user.check_password(data['password']):
        return jsonify({'error': 'Invalid credentials'}), 401
    
    # Generate JWT token
    token_payload = {
        'user_id': user.id,
        'username': user.username,
        'exp': datetime.utcnow() + timedelta(hours=24),
        'iat': datetime.utcnow()
    }
    
    token = jwt.encode(
        token_payload,
        current_app.config['SECRET_KEY'],
        algorithm='HS256'
    )
    
    return jsonify({
        'token': token,
        'user': user_schema.dump(user),
        'expires_in': 86400  # 24 hours
    })


@api_hub.route('/auth/refresh', methods=['POST'])
@login_required
def refresh_token():
    """Refresh JWT token."""
    token_payload = {
        'user_id': current_user.id,
        'username': current_user.username,
        'exp': datetime.utcnow() + timedelta(hours=24),
        'iat': datetime.utcnow()
    }
    
    token = jwt.encode(
        token_payload,
        current_app.config['SECRET_KEY'],
        algorithm='HS256'
    )
    
    return jsonify({
        'token': token,
        'expires_in': 86400
    })


# Knowledge Entry endpoints
@api_hub.route('/entries', methods=['GET'])
@rate_limit('100/hour')
@cache.cached(timeout=300, query_string=True)
def get_entries():
    """Get paginated list of knowledge entries."""
    # Query parameters
    page = request.args.get('page', 1, type=int)
    per_page = min(request.args.get('per_page', 10, type=int), 100)
    category = request.args.get('category')
    search = request.args.get('search')
    sort_by = request.args.get('sort', 'created_desc')
    public_only = request.args.get('public_only', 'true').lower() == 'true'
    
    # Build query
    query = KnowledgeEntry.query
    
    # Apply filters
    if public_only and not current_user.is_authenticated:
        query = query.filter_by(is_public=True)
    elif current_user.is_authenticated and not current_user.is_admin:
        query = query.filter(
            or_(
                KnowledgeEntry.is_public == True,
                KnowledgeEntry.author_id == current_user.id
            )
        )
    
    if category:
        query = query.filter_by(category=category)
    
    if search:
        query = query.filter(
            or_(
                KnowledgeEntry.title.contains(search),
                KnowledgeEntry.content.contains(search),
                KnowledgeEntry.tags.contains(search)
            )
        )
    
    # Apply sorting
    if sort_by == 'created_asc':
        query = query.order_by(asc(KnowledgeEntry.created_at))
    elif sort_by == 'title_asc':
        query = query.order_by(asc(KnowledgeEntry.title))
    elif sort_by == 'title_desc':
        query = query.order_by(desc(KnowledgeEntry.title))
    else:  # created_desc
        query = query.order_by(desc(KnowledgeEntry.created_at))
    
    # Paginate
    pagination_result = paginate_query(query, page, per_page)
    
    return jsonify({
        'entries': knowledge_entries_schema.dump(pagination_result['items']),
        'pagination': pagination_result['pagination']
    })


@api_hub.route('/entries/<int:entry_id>', methods=['GET'])
@rate_limit('200/hour')
def get_entry(entry_id):
    """Get single knowledge entry by ID."""
    entry = KnowledgeEntry.query.get_or_404(entry_id)
    
    # Check permissions
    if not entry.is_public:
        if not current_user.is_authenticated:
            abort(403)
        if entry.author_id != current_user.id and not current_user.is_admin:
            abort(403)
    
    return jsonify({
        'entry': knowledge_entry_schema.dump(entry)
    })


@api_hub.route('/entries', methods=['POST'])
@login_required
@rate_limit('20/hour')
def create_entry():
    """Create new knowledge entry."""
    data = request.get_json()
    
    if not data:
        return jsonify({'error': 'No data provided'}), 400
    
    # Validate required fields
    required_fields = ['title', 'content', 'category']
    for field in required_fields:
        if not data.get(field):
            return jsonify({'error': f'{field} is required'}), 400
    
    try:
        # Create new entry
        entry = KnowledgeEntry(
            title=data['title'],
            description=data.get('description', ''),
            content=data['content'],
            category=data['category'],
            tags=data.get('tags', ''),
            source_url=data.get('source_url'),
            is_public=data.get('is_public', False),
            is_featured=data.get('is_featured', False) if current_user.is_admin else False,
            author_id=current_user.id
        )
        
        db.session.add(entry)
        db.session.commit()
        
        return jsonify({
            'entry': knowledge_entry_schema.dump(entry),
            'message': 'Entry created successfully'
        }), 201
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f'Error creating entry: {e}')
        return jsonify({'error': 'Failed to create entry'}), 500


@api_hub.route('/entries/<int:entry_id>', methods=['PUT'])
@login_required
@rate_limit('30/hour')
def update_entry(entry_id):
    """Update knowledge entry."""
    entry = KnowledgeEntry.query.get_or_404(entry_id)
    
    # Check permissions
    if entry.author_id != current_user.id and not current_user.is_admin:
        abort(403)
    
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided'}), 400
    
    try:
        # Update fields
        if 'title' in data:
            entry.title = data['title']
        if 'description' in data:
            entry.description = data['description']
        if 'content' in data:
            entry.content = data['content']
        if 'category' in data:
            entry.category = data['category']
        if 'tags' in data:
            entry.tags = data['tags']
        if 'source_url' in data:
            entry.source_url = data['source_url']
        if 'is_public' in data:
            entry.is_public = data['is_public']
        if 'is_featured' in data and current_user.is_admin:
            entry.is_featured = data['is_featured']
        
        entry.updated_at = datetime.utcnow()
        db.session.commit()
        
        return jsonify({
            'entry': knowledge_entry_schema.dump(entry),
            'message': 'Entry updated successfully'
        })
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f'Error updating entry: {e}')
        return jsonify({'error': 'Failed to update entry'}), 500


@api_hub.route('/entries/<int:entry_id>', methods=['DELETE'])
@login_required
@rate_limit('10/hour')
def delete_entry(entry_id):
    """Delete knowledge entry."""
    entry = KnowledgeEntry.query.get_or_404(entry_id)
    
    # Check permissions
    if entry.author_id != current_user.id and not current_user.is_admin:
        abort(403)
    
    try:
        db.session.delete(entry)
        db.session.commit()
        
        return jsonify({
            'message': 'Entry deleted successfully'
        })
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f'Error deleting entry: {e}')
        return jsonify({'error': 'Failed to delete entry'}), 500


# User endpoints
@api_hub.route('/users', methods=['GET'])
@login_required
@role_required('admin')
@rate_limit('50/hour')
def get_users():
    """Get paginated list of users (admin only)."""
    page = request.args.get('page', 1, type=int)
    per_page = min(request.args.get('per_page', 10, type=int), 100)
    
    query = User.query.order_by(desc(User.created_at))
    pagination_result = paginate_query(query, page, per_page)
    
    return jsonify({
        'users': users_schema.dump(pagination_result['items']),
        'pagination': pagination_result['pagination']
    })


@api_hub.route('/users/<int:user_id>', methods=['GET'])
@login_required
def get_user(user_id):
    """Get user by ID."""
    # Users can view their own profile or admins can view any profile
    if current_user.id != user_id and not current_user.is_admin:
        abort(403)
    
    user = User.query.get_or_404(user_id)
    return jsonify({
        'user': user_schema.dump(user)
    })


# Statistics endpoints
@api_hub.route('/stats/overview', methods=['GET'])
@rate_limit('10/minute')
@cache.cached(timeout=600)
def get_stats_overview():
    """Get general statistics overview."""
    total_entries = KnowledgeEntry.query.count()
    public_entries = KnowledgeEntry.query.filter_by(is_public=True).count()
    total_users = User.query.count()
    
    # Category breakdown
    categories = db.session.query(
        KnowledgeEntry.category,
        db.func.count(KnowledgeEntry.id).label('count')
    ).filter_by(is_public=True).group_by(KnowledgeEntry.category).all()
    
    # Recent activity (last 30 days)
    thirty_days_ago = datetime.utcnow() - timedelta(days=30)
    recent_entries = KnowledgeEntry.query.filter(
        KnowledgeEntry.created_at >= thirty_days_ago
    ).count()
    
    return jsonify({
        'total_entries': total_entries,
        'public_entries': public_entries,
        'total_users': total_users,
        'recent_entries': recent_entries,
        'categories': [{'name': cat, 'count': count} for cat, count in categories]
    })


@api_hub.route('/categories', methods=['GET'])
@rate_limit('50/hour')
@cache.cached(timeout=300)
def get_categories():
    """Get list of categories with entry counts."""
    categories = db.session.query(
        KnowledgeEntry.category,
        db.func.count(KnowledgeEntry.id).label('count')
    ).filter_by(is_public=True).group_by(KnowledgeEntry.category).all()
    
    return jsonify({
        'categories': [{'name': cat, 'count': count} for cat, count in categories]
    })


@api_hub.route('/search', methods=['GET'])
@rate_limit('100/hour')
def search_entries():
    """Search knowledge entries with advanced options."""
    query_string = request.args.get('q', '').strip()
    category = request.args.get('category')
    author = request.args.get('author')
    date_from = request.args.get('date_from')
    date_to = request.args.get('date_to')
    page = request.args.get('page', 1, type=int)
    per_page = min(request.args.get('per_page', 10, type=int), 100)
    
    if not query_string and not category and not author:
        return jsonify({'error': 'At least one search parameter is required'}), 400
    
    # Build search query
    query = KnowledgeEntry.query
    
    if not current_user.is_authenticated:
        query = query.filter_by(is_public=True)
    elif not current_user.is_admin:
        query = query.filter(
            or_(
                KnowledgeEntry.is_public == True,
                KnowledgeEntry.author_id == current_user.id
            )
        )
    
    if query_string:
        query = query.filter(
            or_(
                KnowledgeEntry.title.contains(query_string),
                KnowledgeEntry.content.contains(query_string),
                KnowledgeEntry.tags.contains(query_string)
            )
        )
    
    if category:
        query = query.filter_by(category=category)
    
    if author:
        user = User.query.filter_by(username=author).first()
        if user:
            query = query.filter_by(author_id=user.id)
    
    if date_from:
        try:
            date_from_obj = datetime.fromisoformat(date_from)
            query = query.filter(KnowledgeEntry.created_at >= date_from_obj)
        except ValueError:
            return jsonify({'error': 'Invalid date_from format'}), 400
    
    if date_to:
        try:
            date_to_obj = datetime.fromisoformat(date_to)
            query = query.filter(KnowledgeEntry.created_at <= date_to_obj)
        except ValueError:
            return jsonify({'error': 'Invalid date_to format'}), 400
    
    query = query.order_by(desc(KnowledgeEntry.created_at))
    pagination_result = paginate_query(query, page, per_page)
    
    return jsonify({
        'entries': knowledge_entries_schema.dump(pagination_result['items']),
        'pagination': pagination_result['pagination'],
        'query': query_string
    })


# Error handlers
@api_hub.errorhandler(404)
def api_not_found(error):
    """API 404 handler."""
    return jsonify({'error': 'Resource not found'}), 404


@api_hub.errorhandler(403)
def api_forbidden(error):
    """API 403 handler."""
    return jsonify({'error': 'Access forbidden'}), 403


@api_hub.errorhandler(400)
def api_bad_request(error):
    """API 400 handler."""
    return jsonify({'error': 'Bad request'}), 400


@api_hub.errorhandler(500)
def api_internal_error(error):
    """API 500 handler."""
    db.session.rollback()
    return jsonify({'error': 'Internal server error'}), 500
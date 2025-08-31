# File: FlaskVerseHub/app/main/routes.py

from flask import render_template, request, jsonify, current_app
from flask_login import current_user
from app.main import bp
from app.models import User, KnowledgeItem, Category, Activity
from app.extensions import db, cache


@bp.route('/')
def index():
    """Homepage route."""
    # Get featured knowledge items
    featured_items = KnowledgeItem.query.filter_by(
        featured=True, status='published'
    ).limit(6).all()
    
    # Get recent items
    recent_items = KnowledgeItem.query.filter_by(
        status='published'
    ).order_by(KnowledgeItem.created_at.desc()).limit(6).all()
    
    # Get popular categories
    popular_categories = Category.query.order_by(
        Category.item_count.desc()
    ).limit(8).all()
    
    # Get stats
    stats = {
        'total_items': KnowledgeItem.query.filter_by(status='published').count(),
        'total_users': User.query.filter_by(is_active=True).count(),
        'total_categories': Category.query.count(),
        'total_views': db.session.query(db.func.sum(KnowledgeItem.view_count)).scalar() or 0
    }
    
    return render_template('main/index.html',
                         featured_items=featured_items,
                         recent_items=recent_items,
                         popular_categories=popular_categories,
                         stats=stats)


@bp.route('/about')
def about():
    """About page."""
    return render_template('main/about.html')


@bp.route('/contact')
def contact():
    """Contact page."""
    return render_template('main/contact.html')


@bp.route('/help')
def help():
    """Help page."""
    return render_template('main/help.html')


@bp.route('/faq')
def faq():
    """FAQ page."""
    return render_template('main/faq.html')


@bp.route('/privacy')
def privacy():
    """Privacy policy page."""
    return render_template('main/privacy.html')


@bp.route('/terms')
def terms():
    """Terms of service page."""
    return render_template('main/terms.html')


@bp.route('/status')
def status():
    """System status page."""
    # Check database connection
    try:
        db.session.execute(db.text('SELECT 1'))
        db_status = 'operational'
    except Exception:
        db_status = 'down'
    
    # Check cache
    try:
        cache.set('health_check', 'ok', timeout=1)
        cache_status = 'operational' if cache.get('health_check') == 'ok' else 'down'
    except Exception:
        cache_status = 'down'
    
    # System info
    system_info = {
        'version': current_app.config.get('APP_VERSION', '1.0.0'),
        'build': current_app.config.get('BUILD_NUMBER', 'dev'),
        'environment': current_app.config.get('FLASK_ENV', 'production')
    }
    
    status_data = {
        'overall': 'operational' if db_status == 'operational' else 'issues',
        'services': {
            'database': db_status,
            'cache': cache_status,
            'api': 'operational',
            'websockets': 'operational'
        },
        'system': system_info
    }
    
    return render_template('main/status.html', status=status_data)


@bp.route('/updates')
def updates():
    """Updates and changelog page."""
    return render_template('main/updates.html')


@bp.route('/changelog')
def changelog():
    """Changelog page."""
    return render_template('main/changelog.html')


@bp.route('/search')
def search():
    """Global search page."""
    query = request.args.get('q', '')
    category_id = request.args.get('category', type=int)
    page = request.args.get('page', 1, type=int)
    per_page = min(request.args.get('per_page', 20, type=int), 100)
    
    if not query:
        return render_template('main/search.html', results=None, query='')
    
    # Build search query
    search_query = KnowledgeItem.query.filter_by(status='published')
    
    # Text search
    search_query = search_query.filter(
        db.or_(
            KnowledgeItem.title.contains(query),
            KnowledgeItem.content.contains(query),
            KnowledgeItem.summary.contains(query)
        )
    )
    
    # Category filter
    if category_id:
        search_query = search_query.filter(
            KnowledgeItem.categories.any(Category.id == category_id)
        )
    
    # Pagination
    results = search_query.order_by(
        KnowledgeItem.created_at.desc()
    ).paginate(
        page=page, per_page=per_page, error_out=False
    )
    
    # Get categories for filter
    categories = Category.query.order_by(Category.name).all()
    
    return render_template('main/search.html',
                         results=results,
                         query=query,
                         categories=categories,
                         selected_category=category_id)


@bp.route('/health')
def health():
    """Health check endpoint for monitoring."""
    try:
        # Check database
        db.session.execute(db.text('SELECT 1'))
        
        health_data = {
            'status': 'healthy',
            'timestamp': db.func.now(),
            'version': current_app.config.get('APP_VERSION', '1.0.0'),
            'services': {
                'database': 'up',
                'cache': 'up' if cache.get('health_check') is not None else 'unknown'
            }
        }
        
        return jsonify(health_data), 200
        
    except Exception as e:
        health_data = {
            'status': 'unhealthy',
            'timestamp': db.func.now(),
            'error': str(e)
        }
        return jsonify(health_data), 503


@bp.route('/stats')
@cache.cached(timeout=300)  # Cache for 5 minutes
def stats():
    """Public statistics API."""
    stats_data = {
        'knowledge_items': KnowledgeItem.query.filter_by(status='published').count(),
        'categories': Category.query.count(),
        'active_users': User.query.filter_by(is_active=True).count(),
        'total_views': db.session.query(db.func.sum(KnowledgeItem.view_count)).scalar() or 0,
        'recent_activity': Activity.query.count()
    }
    
    return jsonify(stats_data)


# Error handlers for main blueprint
@bp.app_errorhandler(404)
def not_found_error(error):
    """Handle 404 errors."""
    return render_template('errors/404.html'), 404


@bp.app_errorhandler(500)
def internal_error(error):
    """Handle 500 errors."""
    db.session.rollback()
    return render_template('errors/500.html'), 500
# File: app/dashboard/routes.py
# 📊 Dashboard Routes

from flask import render_template, request, jsonify, current_app
from flask_login import login_required, current_user
from sqlalchemy import func, desc, asc
from datetime import datetime, timedelta
import json

from . import dashboard
from ..models import KnowledgeEntry, User, db
from ..auth.decorators import role_required
from ..utils.cache_utils import cache


@dashboard.route('/')
@dashboard.route('/index')
@login_required
def index():
    """Main dashboard page."""
    return render_template('dashboard/dashboard.html')


@dashboard.route('/analytics')
@login_required
@role_required('admin')
def analytics():
    """Analytics dashboard page."""
    return render_template('dashboard/analytics.html')


@dashboard.route('/notifications')
@login_required
def notifications():
    """Notifications page."""
    return render_template('dashboard/notifications.html')


# API Endpoints for dashboard data
@dashboard.route('/api/stats/overview')
@login_required
@cache.cached(timeout=300)  # Cache for 5 minutes
def api_stats_overview():
    """Get overview statistics."""
    try:
        # Basic counts
        total_entries = KnowledgeEntry.query.count()
        public_entries = KnowledgeEntry.query.filter_by(is_public=True).count()
        private_entries = total_entries - public_entries
        total_users = User.query.count()
        
        # User's personal stats
        user_entries = KnowledgeEntry.query.filter_by(author_id=current_user.id).count()
        user_public_entries = KnowledgeEntry.query.filter_by(
            author_id=current_user.id, is_public=True
        ).count()
        
        # Recent activity (last 30 days)
        thirty_days_ago = datetime.utcnow() - timedelta(days=30)
        recent_entries = KnowledgeEntry.query.filter(
            KnowledgeEntry.created_at >= thirty_days_ago
        ).count()
        
        recent_user_entries = KnowledgeEntry.query.filter(
            KnowledgeEntry.author_id == current_user.id,
            KnowledgeEntry.created_at >= thirty_days_ago
        ).count()
        
        # Growth data (last 7 days)
        growth_data = []
        for i in range(7):
            date = datetime.utcnow() - timedelta(days=i)
            day_start = date.replace(hour=0, minute=0, second=0, microsecond=0)
            day_end = day_start + timedelta(days=1)
            
            day_entries = KnowledgeEntry.query.filter(
                KnowledgeEntry.created_at >= day_start,
                KnowledgeEntry.created_at < day_end
            ).count()
            
            growth_data.append({
                'date': day_start.strftime('%Y-%m-%d'),
                'entries': day_entries
            })
        
        growth_data.reverse()  # Show oldest first
        
        return jsonify({
            'success': True,
            'data': {
                'global': {
                    'total_entries': total_entries,
                    'public_entries': public_entries,
                    'private_entries': private_entries,
                    'total_users': total_users,
                    'recent_entries': recent_entries
                },
                'user': {
                    'total_entries': user_entries,
                    'public_entries': user_public_entries,
                    'private_entries': user_entries - user_public_entries,
                    'recent_entries': recent_user_entries
                },
                'growth': growth_data
            }
        })
        
    except Exception as e:
        current_app.logger.error(f'Error getting overview stats: {e}')
        return jsonify({'success': False, 'error': 'Failed to load statistics'}), 500


@dashboard.route('/api/stats/categories')
@login_required
@cache.cached(timeout=600)  # Cache for 10 minutes
def api_stats_categories():
    """Get category distribution statistics."""
    try:
        # Global category stats
        global_categories = db.session.query(
            KnowledgeEntry.category,
            func.count(KnowledgeEntry.id).label('count')
        ).filter_by(is_public=True).group_by(KnowledgeEntry.category).all()
        
        # User's category stats
        user_categories = db.session.query(
            KnowledgeEntry.category,
            func.count(KnowledgeEntry.id).label('count')
        ).filter_by(author_id=current_user.id).group_by(KnowledgeEntry.category).all()
        
        # Format data for charts
        global_data = [
            {'name': category, 'value': count}
            for category, count in global_categories
        ]
        
        user_data = [
            {'name': category, 'value': count}
            for category, count in user_categories
        ]
        
        return jsonify({
            'success': True,
            'data': {
                'global': global_data,
                'user': user_data
            }
        })
        
    except Exception as e:
        current_app.logger.error(f'Error getting category stats: {e}')
        return jsonify({'success': False, 'error': 'Failed to load category statistics'}), 500


@dashboard.route('/api/stats/activity')
@login_required
def api_stats_activity():
    """Get activity statistics."""
    try:
        days = request.args.get('days', 30, type=int)
        days = min(days, 365)  # Limit to 1 year
        
        start_date = datetime.utcnow() - timedelta(days=days)
        
        # Daily activity data
        activity_data = []
        for i in range(days):
            date = start_date + timedelta(days=i)
            day_start = date.replace(hour=0, minute=0, second=0, microsecond=0)
            day_end = day_start + timedelta(days=1)
            
            # Total entries created that day
            total_entries = KnowledgeEntry.query.filter(
                KnowledgeEntry.created_at >= day_start,
                KnowledgeEntry.created_at < day_end
            ).count()
            
            # User's entries created that day
            user_entries = KnowledgeEntry.query.filter(
                KnowledgeEntry.author_id == current_user.id,
                KnowledgeEntry.created_at >= day_start,
                KnowledgeEntry.created_at < day_end
            ).count()
            
            activity_data.append({
                'date': day_start.strftime('%Y-%m-%d'),
                'total': total_entries,
                'user': user_entries
            })
        
        return jsonify({
            'success': True,
            'data': activity_data
        })
        
    except Exception as e:
        current_app.logger.error(f'Error getting activity stats: {e}')
        return jsonify({'success': False, 'error': 'Failed to load activity statistics'}), 500


@dashboard.route('/api/recent/entries')
@login_required
def api_recent_entries():
    """Get recent entries."""
    try:
        limit = min(request.args.get('limit', 10, type=int), 50)
        
        # Get user's recent entries
        recent_entries = KnowledgeEntry.query.filter_by(
            author_id=current_user.id
        ).order_by(desc(KnowledgeEntry.created_at)).limit(limit).all()
        
        entries_data = []
        for entry in recent_entries:
            entries_data.append({
                'id': entry.id,
                'title': entry.title,
                'category': entry.category,
                'is_public': entry.is_public,
                'is_featured': entry.is_featured,
                'created_at': entry.created_at.isoformat(),
                'word_count': len(entry.content.split()) if entry.content else 0
            })
        
        return jsonify({
            'success': True,
            'data': entries_data
        })
        
    except Exception as e:
        current_app.logger.error(f'Error getting recent entries: {e}')
        return jsonify({'success': False, 'error': 'Failed to load recent entries'}), 500


@dashboard.route('/api/popular/entries')
@login_required
def api_popular_entries():
    """Get popular entries (public only)."""
    try:
        limit = min(request.args.get('limit', 10, type=int), 50)
        
        # For now, we'll use featured entries as "popular"
        # In a real system, you'd track views/likes
        popular_entries = KnowledgeEntry.query.filter_by(
            is_public=True,
            is_featured=True
        ).order_by(desc(KnowledgeEntry.created_at)).limit(limit).all()
        
        # If no featured entries, fall back to recent public entries
        if not popular_entries:
            popular_entries = KnowledgeEntry.query.filter_by(
                is_public=True
            ).order_by(desc(KnowledgeEntry.created_at)).limit(limit).all()
        
        entries_data = []
        for entry in popular_entries:
            entries_data.append({
                'id': entry.id,
                'title': entry.title,
                'author': entry.author.username if entry.author else 'Unknown',
                'category': entry.category,
                'created_at': entry.created_at.isoformat(),
                'is_featured': entry.is_featured
            })
        
        return jsonify({
            'success': True,
            'data': entries_data
        })
        
    except Exception as e:
        current_app.logger.error(f'Error getting popular entries: {e}')
        return jsonify({'success': False, 'error': 'Failed to load popular entries'}), 500


@dashboard.route('/api/search/suggestions')
@login_required
def api_search_suggestions():
    """Get search suggestions for dashboard quick search."""
    try:
        query = request.args.get('q', '').strip().lower()
        
        if len(query) < 2:
            return jsonify({'success': True, 'data': []})
        
        suggestions = []
        
        # Search in user's entries
        user_entries = KnowledgeEntry.query.filter(
            KnowledgeEntry.author_id == current_user.id,
            KnowledgeEntry.title.contains(query)
        ).limit(5).all()
        
        for entry in user_entries:
            suggestions.append({
                'type': 'entry',
                'title': entry.title,
                'category': entry.category,
                'url': f'/knowledge_vault/entry/{entry.id}',
                'is_own': True
            })
        
        # Search in public entries
        if len(suggestions) < 5:
            public_entries = KnowledgeEntry.query.filter(
                KnowledgeEntry.author_id != current_user.id,
                KnowledgeEntry.is_public == True,
                KnowledgeEntry.title.contains(query)
            ).limit(5 - len(suggestions)).all()
            
            for entry in public_entries:
                suggestions.append({
                    'type': 'entry',
                    'title': entry.title,
                    'category': entry.category,
                    'author': entry.author.username if entry.author else 'Unknown',
                    'url': f'/knowledge_vault/entry/{entry.id}',
                    'is_own': False
                })
        
        return jsonify({
            'success': True,
            'data': suggestions
        })
        
    except Exception as e:
        current_app.logger.error(f'Error getting search suggestions: {e}')
        return jsonify({'success': False, 'error': 'Failed to load suggestions'}), 500


@dashboard.route('/api/notifications')
@login_required
def api_notifications():
    """Get user notifications."""
    try:
        # This is a placeholder - in a real system you'd have a notifications table
        notifications = [
            {
                'id': 1,
                'title': 'Welcome to FlaskVerseHub!',
                'message': 'Thanks for joining our knowledge sharing platform.',
                'type': 'info',
                'created_at': datetime.utcnow().isoformat(),
                'read': False
            }
        ]
        
        # Add some dynamic notifications based on user activity
        user_entries_count = KnowledgeEntry.query.filter_by(author_id=current_user.id).count()
        
        if user_entries_count == 0:
            notifications.append({
                'id': 2,
                'title': 'Create your first entry!',
                'message': 'Start sharing your knowledge by creating your first entry.',
                'type': 'suggestion',
                'created_at': datetime.utcnow().isoformat(),
                'read': False,
                'action_url': '/knowledge_vault/create'
            })
        elif user_entries_count >= 5:
            notifications.append({
                'id': 3,
                'title': 'Great job!',
                'message': f'You have created {user_entries_count} entries. Keep sharing!',
                'type': 'success',
                'created_at': datetime.utcnow().isoformat(),
                'read': False
            })
        
        return jsonify({
            'success': True,
            'data': notifications
        })
        
    except Exception as e:
        current_app.logger.error(f'Error getting notifications: {e}')
        return jsonify({'success': False, 'error': 'Failed to load notifications'}), 500


@dashboard.route('/api/system/health')
@login_required
@role_required('admin')
def api_system_health():
    """Get system health information."""
    try:
        import psutil
        import sys
        
        # System metrics
        cpu_percent = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        
        # Database metrics
        db_size = db.session.execute('SELECT pg_database_size(current_database())').scalar() if 'postgresql' in current_app.config.get('SQLALCHEMY_DATABASE_URI', '') else 0
        
        health_data = {
            'system': {
                'cpu_usage': cpu_percent,
                'memory_usage': memory.percent,
                'memory_available': memory.available,
                'disk_usage': disk.percent,
                'disk_free': disk.free
            },
            'application': {
                'python_version': sys.version,
                'flask_env': current_app.config.get('FLASK_ENV', 'unknown'),
                'debug_mode': current_app.debug
            },
            'database': {
                'size': db_size,
                'total_entries': KnowledgeEntry.query.count(),
                'total_users': User.query.count()
            }
        }
        
        return jsonify({
            'success': True,
            'data': health_data
        })
        
    except Exception as e:
        current_app.logger.error(f'Error getting system health: {e}')
        return jsonify({'success': False, 'error': 'Failed to load system health'}), 500
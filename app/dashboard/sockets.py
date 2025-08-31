# File: app/dashboard/sockets.py
# 📊 Flask-SocketIO Event Handlers

from flask import current_app
from flask_socketio import emit, join_room, leave_room, disconnect
from flask_login import current_user
from datetime import datetime
import json

from ..extensions import socketio
from ..models import KnowledgeEntry, User


@socketio.on('connect', namespace='/dashboard')
def on_connect():
    """Handle client connection to dashboard namespace."""
    if not current_user.is_authenticated:
        disconnect()
        return False
    
    # Join user to their personal room
    join_room(f'user_{current_user.id}')
    
    # Join admin users to admin room
    if current_user.is_admin:
        join_room('admin')
    
    # Send initial connection confirmation
    emit('connected', {
        'message': 'Connected to dashboard',
        'user_id': current_user.id,
        'timestamp': datetime.utcnow().isoformat()
    })
    
    current_app.logger.info(f'User {current_user.username} connected to dashboard')


@socketio.on('disconnect', namespace='/dashboard')
def on_disconnect():
    """Handle client disconnection from dashboard namespace."""
    if current_user.is_authenticated:
        leave_room(f'user_{current_user.id}')
        if current_user.is_admin:
            leave_room('admin')
        
        current_app.logger.info(f'User {current_user.username} disconnected from dashboard')


@socketio.on('join_room', namespace='/dashboard')
def on_join_room(data):
    """Handle joining specific rooms."""
    if not current_user.is_authenticated:
        return
    
    room = data.get('room')
    
    # Validate room access
    if room == 'admin' and not current_user.is_admin:
        emit('error', {'message': 'Access denied to admin room'})
        return
    
    if room == 'notifications':
        join_room(room)
        emit('room_joined', {'room': room, 'message': f'Joined {room} room'})


@socketio.on('leave_room', namespace='/dashboard')
def on_leave_room(data):
    """Handle leaving specific rooms."""
    if not current_user.is_authenticated:
        return
    
    room = data.get('room')
    leave_room(room)
    emit('room_left', {'room': room, 'message': f'Left {room} room'})


@socketio.on('request_stats', namespace='/dashboard')
def on_request_stats():
    """Handle real-time stats request."""
    if not current_user.is_authenticated:
        return
    
    try:
        # Get basic stats
        total_entries = KnowledgeEntry.query.count()
        user_entries = KnowledgeEntry.query.filter_by(author_id=current_user.id).count()
        public_entries = KnowledgeEntry.query.filter_by(is_public=True).count()
        
        stats = {
            'total_entries': total_entries,
            'user_entries': user_entries,
            'public_entries': public_entries,
            'timestamp': datetime.utcnow().isoformat()
        }
        
        emit('stats_update', stats)
        
    except Exception as e:
        current_app.logger.error(f'Error getting real-time stats: {e}')
        emit('error', {'message': 'Failed to get statistics'})


@socketio.on('request_activity', namespace='/dashboard')
def on_request_activity(data):
    """Handle activity data request."""
    if not current_user.is_authenticated:
        return
    
    try:
        hours = data.get('hours', 24)  # Default to last 24 hours
        hours = min(hours, 168)  # Limit to 1 week
        
        from datetime import timedelta
        
        start_time = datetime.utcnow() - timedelta(hours=hours)
        
        # Get recent entries
        recent_entries = KnowledgeEntry.query.filter(
            KnowledgeEntry.created_at >= start_time
        ).order_by(KnowledgeEntry.created_at.desc()).limit(20).all()
        
        activity_data = []
        for entry in recent_entries:
            activity_data.append({
                'id': entry.id,
                'title': entry.title,
                'author': entry.author.username if entry.author else 'Unknown',
                'category': entry.category,
                'created_at': entry.created_at.isoformat(),
                'is_public': entry.is_public
            })
        
        emit('activity_update', {
            'entries': activity_data,
            'period': f'{hours} hours',
            'timestamp': datetime.utcnow().isoformat()
        })
        
    except Exception as e:
        current_app.logger.error(f'Error getting activity data: {e}')
        emit('error', {'message': 'Failed to get activity data'})


@socketio.on('ping', namespace='/dashboard')
def on_ping():
    """Handle ping for connection testing."""
    emit('pong', {'timestamp': datetime.utcnow().isoformat()})


@socketio.on('subscribe_notifications', namespace='/dashboard')
def on_subscribe_notifications():
    """Subscribe to real-time notifications."""
    if not current_user.is_authenticated:
        return
    
    join_room('notifications')
    emit('notification_subscription', {
        'status': 'subscribed',
        'message': 'You will receive real-time notifications'
    })


@socketio.on('unsubscribe_notifications', namespace='/dashboard')
def on_unsubscribe_notifications():
    """Unsubscribe from real-time notifications."""
    if not current_user.is_authenticated:
        return
    
    leave_room('notifications')
    emit('notification_subscription', {
        'status': 'unsubscribed',
        'message': 'Real-time notifications disabled'
    })


@socketio.on('mark_notification_read', namespace='/dashboard')
def on_mark_notification_read(data):
    """Mark notification as read."""
    if not current_user.is_authenticated:
        return
    
    notification_id = data.get('notification_id')
    
    # In a real system, you'd update the notification in the database
    # For now, we'll just acknowledge
    emit('notification_marked_read', {
        'notification_id': notification_id,
        'status': 'read'
    })


# Background task functions (called from routes or other parts of the app)
def notify_entry_created(entry):
    """Notify about new entry creation."""
    try:
        notification_data = {
            'type': 'entry_created',
            'title': 'New Entry Created',
            'message': f'"{entry.title}" has been created',
            'entry_id': entry.id,
            'author': entry.author.username if entry.author else 'Unknown',
            'category': entry.category,
            'timestamp': datetime.utcnow().isoformat()
        }
        
        # Notify the author
        socketio.emit('notification', notification_data, 
                     room=f'user_{entry.author_id}', namespace='/dashboard')
        
        # Notify admins if it's a public entry
        if entry.is_public:
            socketio.emit('admin_notification', notification_data,
                         room='admin', namespace='/dashboard')
        
    except Exception as e:
        current_app.logger.error(f'Error sending entry creation notification: {e}')


def notify_entry_updated(entry):
    """Notify about entry updates."""
    try:
        notification_data = {
            'type': 'entry_updated',
            'title': 'Entry Updated',
            'message': f'"{entry.title}" has been updated',
            'entry_id': entry.id,
            'author': entry.author.username if entry.author else 'Unknown',
            'category': entry.category,
            'timestamp': datetime.utcnow().isoformat()
        }
        
        # Notify the author
        socketio.emit('notification', notification_data,
                     room=f'user_{entry.author_id}', namespace='/dashboard')
        
    except Exception as e:
        current_app.logger.error(f'Error sending entry update notification: {e}')


def notify_system_alert(message, level='info', admin_only=False):
    """Send system-wide notifications."""
    try:
        notification_data = {
            'type': 'system_alert',
            'title': 'System Alert',
            'message': message,
            'level': level,
            'timestamp': datetime.utcnow().isoformat()
        }
        
        if admin_only:
            socketio.emit('admin_notification', notification_data,
                         room='admin', namespace='/dashboard')
        else:
            socketio.emit('system_notification', notification_data,
                         namespace='/dashboard')
        
    except Exception as e:
        current_app.logger.error(f'Error sending system alert: {e}')


def broadcast_stats_update():
    """Broadcast statistics update to all connected users."""
    try:
        total_entries = KnowledgeEntry.query.count()
        public_entries = KnowledgeEntry.query.filter_by(is_public=True).count()
        total_users = User.query.count()
        
        stats_data = {
            'total_entries': total_entries,
            'public_entries': public_entries,
            'total_users': total_users,
            'timestamp': datetime.utcnow().isoformat()
        }
        
        socketio.emit('global_stats_update', stats_data, namespace='/dashboard')
        
    except Exception as e:
        current_app.logger.error(f'Error broadcasting stats update: {e}')


def notify_user_activity(user_id, activity_type, details=None):
    """Notify about user activity."""
    try:
        notification_data = {
            'type': 'user_activity',
            'activity_type': activity_type,
            'details': details or {},
            'timestamp': datetime.utcnow().isoformat()
        }
        
        # Send to user's personal room
        socketio.emit('activity_notification', notification_data,
                     room=f'user_{user_id}', namespace='/dashboard')
        
    except Exception as e:
        current_app.logger.error(f'Error sending activity notification: {e}')


# Error handlers
@socketio.on_error(namespace='/dashboard')
def dashboard_error_handler(e):
    """Handle SocketIO errors in dashboard namespace."""
    current_app.logger.error(f'Dashboard SocketIO error: {e}')
    emit('error', {
        'message': 'An error occurred',
        'timestamp': datetime.utcnow().isoformat()
    })
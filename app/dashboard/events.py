# File: app/dashboard/events.py
# 📊 Real-time Event Management

from flask import current_app
from datetime import datetime, timedelta
from threading import Thread
import time
import json

from ..extensions import socketio
from ..models import KnowledgeEntry, User, db
from .sockets import broadcast_stats_update, notify_system_alert


class EventManager:
    """Manage real-time events and background tasks."""
    
    def __init__(self, app=None):
        self.app = app
        self.active_tasks = {}
        
        if app is not None:
            self.init_app(app)
    
    def init_app(self, app):
        """Initialize event manager with Flask app."""
        self.app = app
        
        # Start background tasks
        if not app.config.get('TESTING'):
            self.start_background_tasks()
    
    def start_background_tasks(self):
        """Start background monitoring tasks."""
        # Start stats update task
        stats_thread = Thread(
            target=self._stats_update_task,
            daemon=True,
            name='stats-updater'
        )
        stats_thread.start()
        self.active_tasks['stats'] = stats_thread
        
        # Start health monitoring task
        health_thread = Thread(
            target=self._health_monitoring_task,
            daemon=True,
            name='health-monitor'
        )
        health_thread.start()
        self.active_tasks['health'] = health_thread
        
        current_app.logger.info('Dashboard background tasks started')
    
    def _stats_update_task(self):
        """Background task to update statistics periodically."""
        while True:
            try:
                with self.app.app_context():
                    # Update stats every 30 seconds
                    broadcast_stats_update()
                    
                time.sleep(30)
                
            except Exception as e:
                current_app.logger.error(f'Error in stats update task: {e}')
                time.sleep(60)  # Wait longer before retrying
    
    def _health_monitoring_task(self):
        """Background task to monitor system health."""
        while True:
            try:
                with self.app.app_context():
                    self._check_system_health()
                    
                time.sleep(300)  # Check every 5 minutes
                
            except Exception as e:
                current_app.logger.error(f'Error in health monitoring task: {e}')
                time.sleep(600)  # Wait longer before retrying
    
    def _check_system_health(self):
        """Check system health and send alerts if needed."""
        try:
            import psutil
            
            # Check CPU usage
            cpu_percent = psutil.cpu_percent(interval=1)
            if cpu_percent > 90:
                notify_system_alert(
                    f'High CPU usage detected: {cpu_percent:.1f}%',
                    level='warning',
                    admin_only=True
                )
            
            # Check memory usage
            memory = psutil.virtual_memory()
            if memory.percent > 90:
                notify_system_alert(
                    f'High memory usage detected: {memory.percent:.1f}%',
                    level='warning',
                    admin_only=True
                )
            
            # Check disk usage
            disk = psutil.disk_usage('/')
            if disk.percent > 85:
                notify_system_alert(
                    f'High disk usage detected: {disk.percent:.1f}%',
                    level='warning',
                    admin_only=True
                )
            
            # Check database connectivity
            try:
                db.session.execute('SELECT 1').scalar()
            except Exception as e:
                notify_system_alert(
                    'Database connectivity issue detected',
                    level='error',
                    admin_only=True
                )
                
        except ImportError:
            # psutil not available, skip system monitoring
            pass
        except Exception as e:
            current_app.logger.error(f'Error checking system health: {e}')


class ActivityTracker:
    """Track user and system activity."""
    
    @staticmethod
    def track_entry_creation(entry):
        """Track entry creation activity."""
        try:
            activity_data = {
                'type': 'entry_created',
                'entry_id': entry.id,
                'title': entry.title,
                'author_id': entry.author_id,
                'category': entry.category,
                'is_public': entry.is_public,
                'timestamp': datetime.utcnow().isoformat()
            }
            
            # Emit to dashboard namespace
            socketio.emit('activity_event', activity_data, namespace='/dashboard')
            
            # Log activity
            current_app.logger.info(f'Entry created: {entry.title} by user {entry.author_id}')
            
        except Exception as e:
            current_app.logger.error(f'Error tracking entry creation: {e}')
    
    @staticmethod
    def track_entry_update(entry):
        """Track entry update activity."""
        try:
            activity_data = {
                'type': 'entry_updated',
                'entry_id': entry.id,
                'title': entry.title,
                'author_id': entry.author_id,
                'category': entry.category,
                'is_public': entry.is_public,
                'timestamp': datetime.utcnow().isoformat()
            }
            
            # Emit to dashboard namespace
            socketio.emit('activity_event', activity_data, namespace='/dashboard')
            
            # Log activity
            current_app.logger.info(f'Entry updated: {entry.title} by user {entry.author_id}')
            
        except Exception as e:
            current_app.logger.error(f'Error tracking entry update: {e}')
    
    @staticmethod
    def track_entry_deletion(entry_data):
        """Track entry deletion activity."""
        try:
            activity_data = {
                'type': 'entry_deleted',
                'entry_id': entry_data.get('id'),
                'title': entry_data.get('title'),
                'author_id': entry_data.get('author_id'),
                'timestamp': datetime.utcnow().isoformat()
            }
            
            # Emit to dashboard namespace
            socketio.emit('activity_event', activity_data, namespace='/dashboard')
            
            # Log activity
            current_app.logger.info(f'Entry deleted: {entry_data.get("title")} by user {entry_data.get("author_id")}')
            
        except Exception as e:
            current_app.logger.error(f'Error tracking entry deletion: {e}')
    
    @staticmethod
    def track_user_login(user):
        """Track user login activity."""
        try:
            activity_data = {
                'type': 'user_login',
                'user_id': user.id,
                'username': user.username,
                'timestamp': datetime.utcnow().isoformat()
            }
            
            # Emit to admin room only
            socketio.emit('admin_activity', activity_data, room='admin', namespace='/dashboard')
            
            # Update user's last login
            user.last_login = datetime.utcnow()
            db.session.commit()
            
        except Exception as e:
            current_app.logger.error(f'Error tracking user login: {e}')
    
    @staticmethod
    def track_user_logout(user):
        """Track user logout activity."""
        try:
            activity_data = {
                'type': 'user_logout',
                'user_id': user.id,
                'username': user.username,
                'timestamp': datetime.utcnow().isoformat()
            }
            
            # Emit to admin room only
            socketio.emit('admin_activity', activity_data, room='admin', namespace='/dashboard')
            
        except Exception as e:
            current_app.logger.error(f'Error tracking user logout: {e}')


class NotificationManager:
    """Manage real-time notifications."""
    
    @staticmethod
    def send_user_notification(user_id, title, message, notification_type='info', action_url=None):
        """Send notification to specific user."""
        try:
            notification_data = {
                'title': title,
                'message': message,
                'type': notification_type,
                'action_url': action_url,
                'timestamp': datetime.utcnow().isoformat(),
                'read': False
            }
            
            # Send to user's room
            socketio.emit('user_notification', notification_data,
                         room=f'user_{user_id}', namespace='/dashboard')
            
        except Exception as e:
            current_app.logger.error(f'Error sending user notification: {e}')
    
    @staticmethod
    def send_admin_notification(title, message, notification_type='info', data=None):
        """Send notification to all admin users."""
        try:
            notification_data = {
                'title': title,
                'message': message,
                'type': notification_type,
                'data': data or {},
                'timestamp': datetime.utcnow().isoformat()
            }
            
            # Send to admin room
            socketio.emit('admin_notification', notification_data,
                         room='admin', namespace='/dashboard')
            
        except Exception as e:
            current_app.logger.error(f'Error sending admin notification: {e}')
    
    @staticmethod
    def broadcast_notification(title, message, notification_type='info'):
        """Broadcast notification to all connected users."""
        try:
            notification_data = {
                'title': title,
                'message': message,
                'type': notification_type,
                'timestamp': datetime.utcnow().isoformat()
            }
            
            # Broadcast to all users in dashboard namespace
            socketio.emit('broadcast_notification', notification_data,
                         namespace='/dashboard')
            
        except Exception as e:
            current_app.logger.error(f'Error broadcasting notification: {e}')


class MetricsCollector:
    """Collect and aggregate metrics for dashboard."""
    
    @staticmethod
    def collect_hourly_metrics():
        """Collect metrics for the current hour."""
        try:
            now = datetime.utcnow()
            hour_start = now.replace(minute=0, second=0, microsecond=0)
            
            metrics = {
                'timestamp': hour_start.isoformat(),
                'entries_created': KnowledgeEntry.query.filter(
                    KnowledgeEntry.created_at >= hour_start,
                    KnowledgeEntry.created_at < hour_start + timedelta(hours=1)
                ).count(),
                'public_entries': KnowledgeEntry.query.filter(
                    KnowledgeEntry.created_at >= hour_start,
                    KnowledgeEntry.created_at < hour_start + timedelta(hours=1),
                    KnowledgeEntry.is_public == True
                ).count(),
                'new_users': User.query.filter(
                    User.created_at >= hour_start,
                    User.created_at < hour_start + timedelta(hours=1)
                ).count(),
                'total_entries': KnowledgeEntry.query.count(),
                'total_users': User.query.count()
            }
            
            # Emit metrics to admin users
            socketio.emit('metrics_update', metrics, room='admin', namespace='/dashboard')
            
            return metrics
            
        except Exception as e:
            current_app.logger.error(f'Error collecting hourly metrics: {e}')
            return None
    
    @staticmethod
    def get_dashboard_summary():
        """Get summary data for dashboard."""
        try:
            now = datetime.utcnow()
            today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
            week_start = today_start - timedelta(days=7)
            
            summary = {
                'today': {
                    'entries': KnowledgeEntry.query.filter(
                        KnowledgeEntry.created_at >= today_start
                    ).count(),
                    'public_entries': KnowledgeEntry.query.filter(
                        KnowledgeEntry.created_at >= today_start,
                        KnowledgeEntry.is_public == True
                    ).count()
                },
                'week': {
                    'entries': KnowledgeEntry.query.filter(
                        KnowledgeEntry.created_at >= week_start
                    ).count(),
                    'public_entries': KnowledgeEntry.query.filter(
                        KnowledgeEntry.created_at >= week_start,
                        KnowledgeEntry.is_public == True
                    ).count()
                },
                'total': {
                    'entries': KnowledgeEntry.query.count(),
                    'users': User.query.count(),
                    'public_entries': KnowledgeEntry.query.filter_by(is_public=True).count()
                }
            }
            
            return summary
            
        except Exception as e:
            current_app.logger.error(f'Error getting dashboard summary: {e}')
            return None


# Event manager instance
event_manager = EventManager()

# Convenience functions for external use
def track_activity(activity_type, **kwargs):
    """Track activity with given type and data."""
    if activity_type == 'entry_created':
        ActivityTracker.track_entry_creation(kwargs.get('entry'))
    elif activity_type == 'entry_updated':
        ActivityTracker.track_entry_update(kwargs.get('entry'))
    elif activity_type == 'entry_deleted':
        ActivityTracker.track_entry_deletion(kwargs.get('entry_data'))
    elif activity_type == 'user_login':
        ActivityTracker.track_user_login(kwargs.get('user'))
    elif activity_type == 'user_logout':
        ActivityTracker.track_user_logout(kwargs.get('user'))


def send_notification(notification_type, **kwargs):
    """Send notification of given type."""
    if notification_type == 'user':
        NotificationManager.send_user_notification(**kwargs)
    elif notification_type == 'admin':
        NotificationManager.send_admin_notification(**kwargs)
    elif notification_type == 'broadcast':
        NotificationManager.broadcast_notification(**kwargs)


def collect_metrics():
    """Collect current metrics."""
    return MetricsCollector.collect_hourly_metrics()


def get_dashboard_data():
    """Get comprehensive dashboard data."""
    return MetricsCollector.get_dashboard_summary()
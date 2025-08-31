# File: app/security/csrf_protection.py
# 🔒 CSRF Token Management

from flask import session, request, abort, current_app
from flask_wtf.csrf import CSRFProtect, CSRFError
import secrets
import hashlib
import hmac


class CSRFManager:
    """Enhanced CSRF protection manager."""
    
    @staticmethod
    def generate_csrf_token():
        """Generate CSRF token."""
        if '_csrf_token' not in session:
            session['_csrf_token'] = secrets.token_urlsafe(32)
        return session['_csrf_token']
    
    @staticmethod
    def validate_csrf_token(token):
        """Validate CSRF token."""
        return token and session.get('_csrf_token') == token
    
    @staticmethod
    def generate_double_submit_token(user_id=None):
        """Generate double-submit CSRF token."""
        secret = current_app.config['SECRET_KEY']
        data = f"{user_id or 'anonymous'}:{request.remote_addr}"
        return hmac.new(
            secret.encode(),
            data.encode(),
            hashlib.sha256
        ).hexdigest()
    
    @staticmethod
    def validate_double_submit_token(token, user_id=None):
        """Validate double-submit CSRF token."""
        expected = CSRFManager.generate_double_submit_token(user_id)
        return hmac.compare_digest(token, expected)


def setup_csrf_protection(app):
    """Setup CSRF protection for the app."""
    csrf = CSRFProtect(app)
    
    @app.template_global()
    def csrf_token():
        return CSRFManager.generate_csrf_token()
    
    @csrf.error_handler
    def csrf_error(reason):
        if request.path.startswith('/api/'):
            from flask import jsonify
            return jsonify({'error': 'CSRF token missing or invalid'}), 400
        abort(400)
    
    return csrf
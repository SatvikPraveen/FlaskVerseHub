# File: app/auth/jwt_utils.py
# 🔐 JWT Token Management

import jwt
from datetime import datetime, timedelta
from flask import current_app
from functools import wraps


class JWTManager:
    """JWT token management utility."""
    
    @staticmethod
    def generate_token(user, expires_delta=None):
        """Generate JWT token for user."""
        if expires_delta is None:
            expires_delta = timedelta(hours=current_app.config.get('JWT_EXPIRATION_HOURS', 24))
        
        payload = {
            'user_id': user.id,
            'username': user.username,
            'email': user.email,
            'is_admin': user.is_admin,
            'iat': datetime.utcnow(),
            'exp': datetime.utcnow() + expires_delta
        }
        
        token = jwt.encode(
            payload,
            current_app.config['SECRET_KEY'],
            algorithm='HS256'
        )
        
        return token
    
    @staticmethod
    def generate_refresh_token(user, expires_delta=None):
        """Generate refresh token for user."""
        if expires_delta is None:
            expires_delta = timedelta(days=current_app.config.get('JWT_REFRESH_EXPIRATION_DAYS', 30))
        
        payload = {
            'user_id': user.id,
            'type': 'refresh',
            'iat': datetime.utcnow(),
            'exp': datetime.utcnow() + expires_delta
        }
        
        token = jwt.encode(
            payload,
            current_app.config['SECRET_KEY'],
            algorithm='HS256'
        )
        
        return token
    
    @staticmethod
    def verify_token(token):
        """Verify and decode JWT token."""
        try:
            payload = jwt.decode(
                token,
                current_app.config['SECRET_KEY'],
                algorithms=['HS256']
            )
            
            # Check if token is expired
            if payload.get('exp', 0) < datetime.utcnow().timestamp():
                return None, 'Token has expired'
            
            return payload, None
        
        except jwt.ExpiredSignatureError:
            return None, 'Token has expired'
        except jwt.InvalidTokenError as e:
            return None, f'Invalid token: {str(e)}'
    
    @staticmethod
    def verify_refresh_token(token):
        """Verify refresh token."""
        payload, error = JWTManager.verify_token(token)
        
        if error:
            return None, error
        
        if payload.get('type') != 'refresh':
            return None, 'Invalid token type'
        
        return payload, None
    
    @staticmethod
    def generate_password_reset_token(user, expires_delta=None):
        """Generate password reset token."""
        if expires_delta is None:
            expires_delta = timedelta(hours=current_app.config.get('PASSWORD_RESET_EXPIRATION_HOURS', 1))
        
        payload = {
            'user_id': user.id,
            'email': user.email,
            'type': 'password_reset',
            'iat': datetime.utcnow(),
            'exp': datetime.utcnow() + expires_delta
        }
        
        token = jwt.encode(
            payload,
            current_app.config['SECRET_KEY'],
            algorithm='HS256'
        )
        
        return token
    
    @staticmethod
    def verify_password_reset_token(token):
        """Verify password reset token."""
        payload, error = JWTManager.verify_token(token)
        
        if error:
            return None, error
        
        if payload.get('type') != 'password_reset':
            return None, 'Invalid token type'
        
        return payload, None
    
    @staticmethod
    def generate_email_verification_token(user, expires_delta=None):
        """Generate email verification token."""
        if expires_delta is None:
            expires_delta = timedelta(days=current_app.config.get('EMAIL_VERIFICATION_EXPIRATION_DAYS', 7))
        
        payload = {
            'user_id': user.id,
            'email': user.email,
            'type': 'email_verification',
            'iat': datetime.utcnow(),
            'exp': datetime.utcnow() + expires_delta
        }
        
        token = jwt.encode(
            payload,
            current_app.config['SECRET_KEY'],
            algorithm='HS256'
        )
        
        return token
    
    @staticmethod
    def verify_email_verification_token(token):
        """Verify email verification token."""
        payload, error = JWTManager.verify_token(token)
        
        if error:
            return None, error
        
        if payload.get('type') != 'email_verification':
            return None, 'Invalid token type'
        
        return payload, None
    
    @staticmethod
    def generate_api_token(user, expires_delta=None, scopes=None):
        """Generate API token with optional scopes."""
        if expires_delta is None:
            expires_delta = timedelta(days=current_app.config.get('API_TOKEN_EXPIRATION_DAYS', 365))
        
        payload = {
            'user_id': user.id,
            'username': user.username,
            'type': 'api_token',
            'scopes': scopes or ['read', 'write'],
            'iat': datetime.utcnow(),
            'exp': datetime.utcnow() + expires_delta
        }
        
        token = jwt.encode(
            payload,
            current_app.config['SECRET_KEY'],
            algorithm='HS256'
        )
        
        return token
    
    @staticmethod
    def verify_api_token(token):
        """Verify API token."""
        payload, error = JWTManager.verify_token(token)
        
        if error:
            return None, error
        
        if payload.get('type') != 'api_token':
            return None, 'Invalid token type'
        
        return payload, None
    
    @staticmethod
    def decode_token_payload(token):
        """Decode token without verification (for debugging)."""
        try:
            payload = jwt.decode(
                token,
                options={"verify_signature": False}
            )
            return payload
        except Exception as e:
            return None
    
    @staticmethod
    def is_token_expired(token):
        """Check if token is expired without full verification."""
        payload = JWTManager.decode_token_payload(token)
        if not payload:
            return True
        
        exp = payload.get('exp', 0)
        return exp < datetime.utcnow().timestamp()
    
    @staticmethod
    def get_token_expiry(token):
        """Get token expiry datetime."""
        payload = JWTManager.decode_token_payload(token)
        if not payload:
            return None
        
        exp = payload.get('exp')
        if exp:
            return datetime.fromtimestamp(exp)
        return None
    
    @staticmethod
    def refresh_access_token(refresh_token):
        """Generate new access token from refresh token."""
        payload, error = JWTManager.verify_refresh_token(refresh_token)
        
        if error:
            return None, error
        
        # Get user from database
        from ..models import User
        user = User.query.get(payload['user_id'])
        
        if not user or not user.is_active:
            return None, 'User not found or inactive'
        
        # Generate new access token
        new_token = JWTManager.generate_token(user)
        
        return new_token, None
    
    @staticmethod
    def revoke_token(token, revoked_tokens_storage=None):
        """Revoke token by adding to blacklist."""
        payload = JWTManager.decode_token_payload(token)
        if not payload:
            return False
        
        # In a real implementation, you'd store revoked tokens in Redis or database
        # For now, we'll just return True
        if revoked_tokens_storage:
            jti = payload.get('jti', token[:10])  # Use JTI or token prefix as identifier
            exp = payload.get('exp', 0)
            revoked_tokens_storage.set(f'revoked_token_{jti}', '1', ex=exp - int(datetime.utcnow().timestamp()))
        
        return True
    
    @staticmethod
    def is_token_revoked(token, revoked_tokens_storage=None):
        """Check if token is revoked."""
        if not revoked_tokens_storage:
            return False
        
        payload = JWTManager.decode_token_payload(token)
        if not payload:
            return True  # Consider invalid tokens as revoked
        
        jti = payload.get('jti', token[:10])
        return revoked_tokens_storage.exists(f'revoked_token_{jti}')


# Convenience functions
def create_access_token(user, expires_delta=None):
    """Create access token for user."""
    return JWTManager.generate_token(user, expires_delta)


def create_refresh_token(user, expires_delta=None):
    """Create refresh token for user."""
    return JWTManager.generate_refresh_token(user, expires_delta)


def verify_jwt_token(token):
    """Verify JWT token."""
    return JWTManager.verify_token(token)


def create_password_reset_token(user):
    """Create password reset token."""
    return JWTManager.generate_password_reset_token(user)


def verify_password_reset_token(token):
    """Verify password reset token."""
    return JWTManager.verify_password_reset_token(token)


def create_email_verification_token(user):
    """Create email verification token."""
    return JWTManager.generate_email_verification_token(user)


def verify_email_verification_token(token):
    """Verify email verification token."""
    return JWTManager.verify_email_verification_token(token)


def create_api_token(user, scopes=None):
    """Create API token for user."""
    return JWTManager.generate_api_token(user, scopes=scopes)


def verify_api_token(token):
    """Verify API token."""
    return JWTManager.verify_api_token(token)


# JWT decorators using the utility functions
def jwt_required(optional=False, refresh=False):
    """Decorator to require JWT authentication."""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            from flask import request, jsonify
            
            token = None
            auth_header = request.headers.get('Authorization')
            
            if auth_header:
                try:
                    scheme, token = auth_header.split(' ', 1)
                    if scheme.lower() != 'bearer':
                        token = None
                except ValueError:
                    token = None
            
            if not token and not optional:
                return jsonify({'error': 'Missing Authorization header'}), 401
            
            if token:
                if refresh:
                    payload, error = JWTManager.verify_refresh_token(token)
                else:
                    payload, error = JWTManager.verify_token(token)
                
                if error and not optional:
                    return jsonify({'error': error}), 401
                
                if payload:
                    # Add token info to request context
                    request.jwt_payload = payload
                    request.jwt_user_id = payload.get('user_id')
                    request.jwt_username = payload.get('username')
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator
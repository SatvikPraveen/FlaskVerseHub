# File: app/security/password_utils.py
# 🔒 Password Hashing and Validation

import re
import secrets
import string
from werkzeug.security import generate_password_hash, check_password_hash


class PasswordValidator:
    """Password validation utilities."""
    
    @staticmethod
    def validate_strength(password):
        """Validate password strength."""
        errors = []
        
        if len(password) < 8:
            errors.append("Password must be at least 8 characters long")
        
        if not re.search(r"[a-z]", password):
            errors.append("Password must contain at least one lowercase letter")
        
        if not re.search(r"[A-Z]", password):
            errors.append("Password must contain at least one uppercase letter")
        
        if not re.search(r"\d", password):
            errors.append("Password must contain at least one digit")
        
        if not re.search(r"[!@#$%^&*(),.?\":{}|<>]", password):
            errors.append("Password must contain at least one special character")
        
        # Check for common patterns
        if re.search(r"(.)\1{2,}", password):
            errors.append("Password cannot contain repeated characters")
        
        return len(errors) == 0, errors
    
    @staticmethod
    def check_common_passwords(password):
        """Check against common passwords."""
        common_passwords = [
            'password', '123456', '123456789', 'qwerty', 'abc123',
            'password123', 'admin', 'letmein', 'welcome', 'monkey'
        ]
        return password.lower() not in common_passwords
    
    @staticmethod
    def generate_secure_password(length=12):
        """Generate secure random password."""
        alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
        return ''.join(secrets.choice(alphabet) for _ in range(length))


class PasswordHasher:
    """Enhanced password hashing."""
    
    @staticmethod
    def hash_password(password, method='pbkdf2:sha256:150000'):
        """Hash password with specified method."""
        return generate_password_hash(password, method=method)
    
    @staticmethod
    def verify_password(password, hash):
        """Verify password against hash."""
        return check_password_hash(hash, password)
    
    @staticmethod
    def needs_rehashing(hash, method='pbkdf2:sha256:150000'):
        """Check if password hash needs updating."""
        return not hash.startswith(method.split(':')[1])


def validate_password_policy(password, username=None, email=None):
    """Comprehensive password policy validation."""
    is_strong, strength_errors = PasswordValidator.validate_strength(password)
    
    errors = []
    if not is_strong:
        errors.extend(strength_errors)
    
    if not PasswordValidator.check_common_passwords(password):
        errors.append("Password is too common")
    
    # Check if password contains username or email
    if username and username.lower() in password.lower():
        errors.append("Password cannot contain your username")
    
    if email:
        email_local = email.split('@')[0].lower()
        if email_local in password.lower():
            errors.append("Password cannot contain your email")
    
    return len(errors) == 0, errors
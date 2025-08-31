# File: app/security/input_sanitization.py
# 🔒 XSS Protection Utilities

import re
import html
import urllib.parse
from markupsafe import Markup


class InputSanitizer:
    """Input sanitization utilities."""
    
    # Allowed HTML tags for content
    ALLOWED_TAGS = {
        'p', 'br', 'strong', 'b', 'em', 'i', 'u', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
        'ul', 'ol', 'li', 'blockquote', 'code', 'pre', 'a', 'img'
    }
    
    # Allowed attributes
    ALLOWED_ATTRIBUTES = {
        'a': ['href', 'title'],
        'img': ['src', 'alt', 'title', 'width', 'height'],
        'blockquote': ['cite']
    }
    
    @staticmethod
    def sanitize_html(content, allowed_tags=None, allowed_attributes=None):
        """Sanitize HTML content to prevent XSS."""
        if not content:
            return ''
        
        if allowed_tags is None:
            allowed_tags = InputSanitizer.ALLOWED_TAGS
        
        if allowed_attributes is None:
            allowed_attributes = InputSanitizer.ALLOWED_ATTRIBUTES
        
        # Basic HTML escaping
        content = html.escape(content)
        
        # Allow specific safe tags
        for tag in allowed_tags:
            # Simple tag replacement (basic implementation)
            content = re.sub(
                f'&lt;{tag}&gt;(.*?)&lt;/{tag}&gt;',
                f'<{tag}>\\1</{tag}>',
                content,
                flags=re.IGNORECASE | re.DOTALL
            )
            
            # Self-closing tags
            content = re.sub(
                f'&lt;{tag}/&gt;',
                f'<{tag}/>',
                content,
                flags=re.IGNORECASE
            )
        
        return Markup(content)
    
    @staticmethod
    def sanitize_text(text):
        """Sanitize plain text input."""
        if not text:
            return ''
        
        # Remove null bytes
        text = text.replace('\x00', '')
        
        # Normalize whitespace
        text = re.sub(r'\s+', ' ', text).strip()
        
        return text
    
    @staticmethod
    def sanitize_filename(filename):
        """Sanitize filename for safe storage."""
        if not filename:
            return ''
        
        # Remove path separators
        filename = filename.replace('/', '').replace('\\', '')
        
        # Remove dangerous characters
        filename = re.sub(r'[<>:"|?*]', '', filename)
        
        # Remove leading/trailing dots and spaces
        filename = filename.strip('. ')
        
        # Limit length
        if len(filename) > 255:
            name, ext = filename.rsplit('.', 1) if '.' in filename else (filename, '')
            filename = name[:255-len(ext)-1] + ('.' + ext if ext else '')
        
        return filename
    
    @staticmethod
    def sanitize_url(url):
        """Sanitize URL to prevent malicious redirects."""
        if not url:
            return ''
        
        # Parse URL
        parsed = urllib.parse.urlparse(url)
        
        # Only allow http/https schemes
        if parsed.scheme and parsed.scheme not in ['http', 'https']:
            return ''
        
        # Reconstruct clean URL
        return urllib.parse.urlunparse(parsed)
    
    @staticmethod
    def strip_tags(content):
        """Strip all HTML tags from content."""
        if not content:
            return ''
        
        # Remove HTML tags
        content = re.sub(r'<[^>]+>', '', content)
        
        # Decode HTML entities
        content = html.unescape(content)
        
        return content.strip()
    
    @staticmethod
    def validate_email_format(email):
        """Validate email format."""
        if not email:
            return False
        
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return re.match(pattern, email) is not None
    
    @staticmethod
    def sanitize_search_query(query):
        """Sanitize search query to prevent injection."""
        if not query:
            return ''
        
        # Remove potentially dangerous characters
        query = re.sub(r'[;\'\"\\]', '', query)
        
        # Limit length
        query = query[:200]
        
        # Normalize whitespace
        query = re.sub(r'\s+', ' ', query).strip()
        
        return query


def clean_input(data):
    """Clean user input data."""
    if isinstance(data, str):
        return InputSanitizer.sanitize_text(data)
    elif isinstance(data, dict):
        return {k: clean_input(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [clean_input(item) for item in data]
    else:
        return data


def sanitize_form_data(form):
    """Sanitize all form data."""
    for field in form:
        if hasattr(field, 'data') and isinstance(field.data, str):
            field.data = InputSanitizer.sanitize_text(field.data)
    return form
# File: app/knowledge_vault/forms.py
# 📚 Knowledge Vault Forms for Validation

from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, SelectField, FileField, BooleanField
from wtforms.validators import DataRequired, Length, Optional, URL
from flask_wtf.file import FileField, FileAllowed


class KnowledgeEntryForm(FlaskForm):
    """Form for creating and editing knowledge vault entries."""
    
    title = StringField(
        'Title',
        validators=[
            DataRequired(message='Title is required'),
            Length(min=3, max=200, message='Title must be between 3 and 200 characters')
        ],
        render_kw={'placeholder': 'Enter knowledge entry title'}
    )
    
    description = TextAreaField(
        'Description',
        validators=[
            Optional(),
            Length(max=500, message='Description cannot exceed 500 characters')
        ],
        render_kw={'placeholder': 'Brief description of this knowledge entry', 'rows': 3}
    )
    
    content = TextAreaField(
        'Content',
        validators=[
            DataRequired(message='Content is required'),
            Length(min=10, message='Content must be at least 10 characters long')
        ],
        render_kw={'placeholder': 'Enter the knowledge content here...', 'rows': 15}
    )
    
    category = SelectField(
        'Category',
        choices=[
            ('general', 'General'),
            ('technical', 'Technical'),
            ('business', 'Business'),
            ('research', 'Research'),
            ('documentation', 'Documentation'),
            ('tutorial', 'Tutorial'),
            ('reference', 'Reference')
        ],
        validators=[DataRequired(message='Please select a category')]
    )
    
    tags = StringField(
        'Tags',
        validators=[
            Optional(),
            Length(max=200, message='Tags cannot exceed 200 characters')
        ],
        render_kw={'placeholder': 'Comma-separated tags (e.g., python, flask, web-development)'}
    )
    
    source_url = StringField(
        'Source URL',
        validators=[
            Optional(),
            URL(message='Please enter a valid URL')
        ],
        render_kw={'placeholder': 'https://example.com/source'}
    )
    
    attachment = FileField(
        'Attachment',
        validators=[
            Optional(),
            FileAllowed(['pdf', 'doc', 'docx', 'txt', 'md'], 'Only PDF, DOC, DOCX, TXT, and MD files allowed')
        ]
    )
    
    is_public = BooleanField(
        'Make this entry public',
        default=False
    )
    
    is_featured = BooleanField(
        'Feature this entry',
        default=False
    )


class SearchForm(FlaskForm):
    """Form for searching knowledge vault entries."""
    
    query = StringField(
        'Search Query',
        validators=[
            DataRequired(message='Search query is required'),
            Length(min=1, max=100, message='Search query must be between 1 and 100 characters')
        ],
        render_kw={'placeholder': 'Search knowledge vault...', 'class': 'form-control'}
    )
    
    category = SelectField(
        'Category',
        choices=[
            ('', 'All Categories'),
            ('general', 'General'),
            ('technical', 'Technical'),
            ('business', 'Business'),
            ('research', 'Research'),
            ('documentation', 'Documentation'),
            ('tutorial', 'Tutorial'),
            ('reference', 'Reference')
        ],
        validators=[Optional()]
    )


class BulkDeleteForm(FlaskForm):
    """Form for bulk operations."""
    
    entry_ids = StringField(
        'Entry IDs',
        validators=[DataRequired(message='Entry IDs are required')]
    )
    
    action = SelectField(
        'Action',
        choices=[
            ('delete', 'Delete'),
            ('archive', 'Archive'),
            ('unarchive', 'Unarchive'),
            ('make_public', 'Make Public'),
            ('make_private', 'Make Private')
        ],
        validators=[DataRequired(message='Please select an action')]
    )
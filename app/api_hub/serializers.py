# File: app/api_hub/serializers.py
# 🔌 Marshmallow Data Serialization

from marshmallow import Schema, fields, validate, post_load, pre_dump
from datetime import datetime


class UserSchema(Schema):
    """User serialization schema."""
    
    id = fields.Integer(dump_only=True)
    username = fields.String(required=True, validate=validate.Length(min=3, max=80))
    email = fields.Email(required=True)
    first_name = fields.String(validate=validate.Length(max=100))
    last_name = fields.String(validate=validate.Length(max=100))
    is_admin = fields.Boolean(dump_only=True)
    is_active = fields.Boolean(dump_only=True)
    created_at = fields.DateTime(dump_only=True, format='iso')
    updated_at = fields.DateTime(dump_only=True, format='iso')
    last_login = fields.DateTime(dump_only=True, format='iso')
    entry_count = fields.Method('get_entry_count', dump_only=True)
    
    def get_entry_count(self, obj):
        """Get the number of public entries by this user."""
        return obj.knowledge_entries.filter_by(is_public=True).count()
    
    class Meta:
        ordered = True


class KnowledgeEntrySchema(Schema):
    """Knowledge entry serialization schema."""
    
    id = fields.Integer(dump_only=True)
    title = fields.String(required=True, validate=validate.Length(min=3, max=200))
    description = fields.String(validate=validate.Length(max=500))
    content = fields.String(required=True, validate=validate.Length(min=10))
    category = fields.String(
        required=True,
        validate=validate.OneOf([
            'general', 'technical', 'business', 'research',
            'documentation', 'tutorial', 'reference'
        ])
    )
    tags = fields.String(validate=validate.Length(max=200))
    source_url = fields.Url()
    attachment_filename = fields.String(dump_only=True)
    is_public = fields.Boolean()
    is_featured = fields.Boolean()
    created_at = fields.DateTime(dump_only=True, format='iso')
    updated_at = fields.DateTime(dump_only=True, format='iso')
    
    # Relationships
    author_id = fields.Integer(dump_only=True)
    author = fields.Nested(UserSchema, dump_only=True, exclude=['entry_count'])
    
    # Computed fields
    word_count = fields.Method('get_word_count', dump_only=True)
    reading_time = fields.Method('get_reading_time', dump_only=True)
    tags_list = fields.Method('get_tags_list', dump_only=True)
    excerpt = fields.Method('get_excerpt', dump_only=True)
    
    def get_word_count(self, obj):
        """Calculate word count of content."""
        return len(obj.content.split()) if obj.content else 0
    
    def get_reading_time(self, obj):
        """Estimate reading time in minutes (assuming 200 words per minute)."""
        word_count = self.get_word_count(obj)
        return max(1, round(word_count / 200))
    
    def get_tags_list(self, obj):
        """Convert comma-separated tags to list."""
        if obj.tags:
            return [tag.strip() for tag in obj.tags.split(',') if tag.strip()]
        return []
    
    def get_excerpt(self, obj):
        """Generate excerpt from content."""
        if obj.content:
            # Remove HTML tags and truncate
            import re
            clean_content = re.sub(r'<[^>]+>', '', obj.content)
            return clean_content[:200] + '...' if len(clean_content) > 200 else clean_content
        return ''
    
    @pre_dump
    def process_entry(self, data, **kwargs):
        """Pre-process data before dumping."""
        # Add any additional processing here
        return data
    
    class Meta:
        ordered = True


class KnowledgeEntryDetailSchema(KnowledgeEntrySchema):
    """Extended schema for detailed entry view."""
    
    # Include full content and additional metadata
    view_count = fields.Method('get_view_count', dump_only=True)
    related_entries = fields.Method('get_related_entries', dump_only=True)
    
    def get_view_count(self, obj):
        """Get view count (placeholder - would need to implement view tracking)."""
        return getattr(obj, 'view_count', 0)
    
    def get_related_entries(self, obj):
        """Get related entries based on category and tags."""
        from ..models import KnowledgeEntry
        from sqlalchemy import or_, and_
        
        # Find entries with same category or matching tags
        related = KnowledgeEntry.query.filter(
            and_(
                KnowledgeEntry.id != obj.id,
                KnowledgeEntry.is_public == True,
                or_(
                    KnowledgeEntry.category == obj.category,
                    KnowledgeEntry.tags.contains(obj.tags.split(',')[0] if obj.tags else '')
                )
            )
        ).limit(5).all()
        
        return KnowledgeEntrySchema(many=True, exclude=['content', 'author']).dump(related)


class CommentSchema(Schema):
    """Comment serialization schema (for future use)."""
    
    id = fields.Integer(dump_only=True)
    content = fields.String(required=True, validate=validate.Length(min=1, max=1000))
    author_id = fields.Integer(dump_only=True)
    entry_id = fields.Integer(required=True)
    created_at = fields.DateTime(dump_only=True, format='iso')
    updated_at = fields.DateTime(dump_only=True, format='iso')
    
    # Relationships
    author = fields.Nested(UserSchema, dump_only=True, only=['id', 'username'])
    
    class Meta:
        ordered = True


class TagSchema(Schema):
    """Tag serialization schema."""
    
    name = fields.String(required=True, validate=validate.Length(min=1, max=50))
    usage_count = fields.Integer(dump_only=True)
    color = fields.String(dump_only=True)
    
    class Meta:
        ordered = True


class CategorySchema(Schema):
    """Category serialization schema."""
    
    name = fields.String(required=True)
    display_name = fields.String(dump_only=True)
    entry_count = fields.Integer(dump_only=True)
    description = fields.String(dump_only=True)
    color = fields.String(dump_only=True)
    
    class Meta:
        ordered = True


class SearchResultSchema(Schema):
    """Search result serialization schema."""
    
    entries = fields.Nested(KnowledgeEntrySchema, many=True)
    total_results = fields.Integer()
    query = fields.String()
    filters_applied = fields.Dict()
    search_time = fields.Float()
    suggestions = fields.List(fields.String())
    
    class Meta:
        ordered = True


class StatisticsSchema(Schema):
    """Statistics serialization schema."""
    
    total_entries = fields.Integer()
    public_entries = fields.Integer()
    private_entries = fields.Integer()
    total_users = fields.Integer()
    active_users = fields.Integer()
    entries_by_category = fields.List(fields.Nested(CategorySchema))
    recent_activity = fields.Dict()
    popular_tags = fields.List(fields.Nested(TagSchema))
    
    class Meta:
        ordered = True


class PaginationSchema(Schema):
    """Pagination metadata schema."""
    
    page = fields.Integer()
    pages = fields.Integer()
    per_page = fields.Integer()
    total = fields.Integer()
    has_next = fields.Boolean()
    has_prev = fields.Boolean()
    next_url = fields.String()
    prev_url = fields.String()
    
    class Meta:
        ordered = True


class ErrorSchema(Schema):
    """Error response schema."""
    
    error = fields.String(required=True)
    message = fields.String()
    code = fields.Integer()
    details = fields.Dict()
    timestamp = fields.DateTime(format='iso')
    
    @pre_dump
    def add_timestamp(self, data, **kwargs):
        """Add timestamp to error response."""
        if isinstance(data, dict) and 'timestamp' not in data:
            data['timestamp'] = datetime.utcnow()
        return data
    
    class Meta:
        ordered = True


class SuccessSchema(Schema):
    """Success response schema."""
    
    message = fields.String(required=True)
    data = fields.Raw()
    timestamp = fields.DateTime(format='iso')
    
    @pre_dump
    def add_timestamp(self, data, **kwargs):
        """Add timestamp to success response."""
        if isinstance(data, dict) and 'timestamp' not in data:
            data['timestamp'] = datetime.utcnow()
        return data
    
    class Meta:
        ordered = True


# Schema instances
user_schema = UserSchema()
users_schema = UserSchema(many=True)

knowledge_entry_schema = KnowledgeEntrySchema()
knowledge_entries_schema = KnowledgeEntrySchema(many=True)

knowledge_entry_detail_schema = KnowledgeEntryDetailSchema()

comment_schema = CommentSchema()
comments_schema = CommentSchema(many=True)

tag_schema = TagSchema()
tags_schema = TagSchema(many=True)

category_schema = CategorySchema()
categories_schema = CategorySchema(many=True)

search_result_schema = SearchResultSchema()
statistics_schema = StatisticsSchema()
pagination_schema = PaginationSchema()
error_schema = ErrorSchema()
success_schema = SuccessSchema()


# Utility functions for serialization
def serialize_with_pagination(items, pagination, schema):
    """Serialize items with pagination metadata."""
    return {
        'data': schema.dump(items),
        'pagination': {
            'page': pagination.page,
            'pages': pagination.pages,
            'per_page': pagination.per_page,
            'total': pagination.total,
            'has_next': pagination.has_next,
            'has_prev': pagination.has_prev
        }
    }


def serialize_error(error_message, code=400, details=None):
    """Serialize error response."""
    return error_schema.dump({
        'error': error_message,
        'code': code,
        'details': details or {}
    })


def serialize_success(message, data=None):
    """Serialize success response."""
    return success_schema.dump({
        'message': message,
        'data': data
    })
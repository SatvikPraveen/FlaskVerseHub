# File: app/api_hub/schemas.py
# 🔌 GraphQL Schema Definitions

import graphene
from graphene import relay, ObjectType, String, Int, Boolean, DateTime, List, Field
from graphene_sqlalchemy import SQLAlchemyObjectType, SQLAlchemyConnectionField
from datetime import datetime

from ..models import KnowledgeEntry as KnowledgeEntryModel, User as UserModel


class UserType(SQLAlchemyObjectType):
    """GraphQL User type definition."""
    
    class Meta:
        model = UserModel
        interfaces = (relay.Node,)
        exclude_fields = ('password_hash',)  # Never expose password
    
    # Additional computed fields
    full_name = String()
    entry_count = Int()
    public_entry_count = Int()
    is_online = Boolean()
    
    def resolve_full_name(self, info):
        """Get user's full name."""
        if self.first_name and self.last_name:
            return f"{self.first_name} {self.last_name}"
        return self.username
    
    def resolve_entry_count(self, info):
        """Get total entries by user."""
        return self.knowledge_entries.count()
    
    def resolve_public_entry_count(self, info):
        """Get public entries by user."""
        return self.knowledge_entries.filter_by(is_public=True).count()
    
    def resolve_is_online(self, info):
        """Check if user is currently online."""
        if not self.last_login:
            return False
        
        # Consider user online if last login was within 15 minutes
        from datetime import datetime, timedelta
        return datetime.utcnow() - self.last_login < timedelta(minutes=15)


class KnowledgeEntryType(SQLAlchemyObjectType):
    """GraphQL KnowledgeEntry type definition."""
    
    class Meta:
        model = KnowledgeEntryModel
        interfaces = (relay.Node,)
    
    # Additional computed fields
    word_count = Int()
    reading_time = Int()
    tags_list = List(String)
    excerpt = String()
    related_entries = List(lambda: KnowledgeEntryType)
    view_count = Int()
    is_bookmarked = Boolean()
    
    def resolve_word_count(self, info):
        """Calculate word count."""
        if not self.content:
            return 0
        import re
        # Remove HTML tags and count words
        clean_content = re.sub(r'<[^>]+>', '', self.content)
        return len(clean_content.split())
    
    def resolve_reading_time(self, info):
        """Estimate reading time in minutes."""
        word_count = self.resolve_word_count(info)
        return max(1, round(word_count / 200))  # 200 words per minute
    
    def resolve_tags_list(self, info):
        """Convert comma-separated tags to list."""
        if not self.tags:
            return []
        return [tag.strip() for tag in self.tags.split(',') if tag.strip()]
    
    def resolve_excerpt(self, info):
        """Generate content excerpt."""
        if not self.content:
            return ''
        
        import re
        clean_content = re.sub(r'<[^>]+>', '', self.content)
        return clean_content[:200] + '...' if len(clean_content) > 200 else clean_content
    
    def resolve_related_entries(self, info):
        """Get related entries based on category and tags."""
        from sqlalchemy import or_, and_
        
        # Find entries with same category or matching tags
        related = KnowledgeEntryModel.query.filter(
            and_(
                KnowledgeEntryModel.id != self.id,
                KnowledgeEntryModel.is_public == True,
                or_(
                    KnowledgeEntryModel.category == self.category,
                    KnowledgeEntryModel.tags.contains(self.tags.split(',')[0] if self.tags else '')
                )
            )
        ).limit(5).all()
        
        return related
    
    def resolve_view_count(self, info):
        """Get view count (placeholder)."""
        # This would need to be implemented with a view tracking system
        return getattr(self, 'view_count', 0)
    
    def resolve_is_bookmarked(self, info):
        """Check if current user bookmarked this entry."""
        # This would need to be implemented with a bookmarking system
        return False


class CategoryType(ObjectType):
    """Category information type."""
    
    name = String(required=True)
    display_name = String()
    entry_count = Int()
    description = String()
    color = String()


class TagType(ObjectType):
    """Tag information type."""
    
    name = String(required=True)
    usage_count = Int()
    color = String()


class StatisticsType(ObjectType):
    """Statistics type."""
    
    total_entries = Int()
    public_entries = Int()
    private_entries = Int()
    total_users = Int()
    active_users = Int()
    entries_by_category = List(CategoryType)
    popular_tags = List(TagType)
    recent_activity = String()  # JSON string


class SearchResultType(ObjectType):
    """Search result type."""
    
    entries = List(KnowledgeEntryType)
    total_results = Int()
    query = String()
    search_time = String()
    suggestions = List(String)


class PaginationInfoType(ObjectType):
    """Pagination information type."""
    
    page = Int()
    pages = Int()
    per_page = Int()
    total = Int()
    has_next = Boolean()
    has_prev = Boolean()
    next_url = String()
    prev_url = String()


# Input types for mutations
class CreateUserInput(graphene.InputObjectType):
    """Input for creating users."""
    
    username = String(required=True)
    email = String(required=True)
    password = String(required=True)
    first_name = String()
    last_name = String()


class UpdateUserInput(graphene.InputObjectType):
    """Input for updating users."""
    
    id = graphene.ID(required=True)
    username = String()
    email = String()
    first_name = String()
    last_name = String()
    is_active = Boolean()
    is_admin = Boolean()


class CreateKnowledgeEntryInput(graphene.InputObjectType):
    """Input for creating knowledge entries."""
    
    title = String(required=True)
    description = String()
    content = String(required=True)
    category = String(required=True)
    tags = String()
    source_url = String()
    is_public = Boolean()
    is_featured = Boolean()


class UpdateKnowledgeEntryInput(graphene.InputObjectType):
    """Input for updating knowledge entries."""
    
    id = graphene.ID(required=True)
    title = String()
    description = String()
    content = String()
    category = String()
    tags = String()
    source_url = String()
    is_public = Boolean()
    is_featured = Boolean()


class SearchInput(graphene.InputObjectType):
    """Input for search operations."""
    
    query = String(required=True)
    category = String()
    author = String()
    date_from = DateTime()
    date_to = DateTime()
    page = Int()
    per_page = Int()


class FilterInput(graphene.InputObjectType):
    """Input for filtering operations."""
    
    category = String()
    is_public = Boolean()
    is_featured = Boolean()
    author_id = Int()
    created_after = DateTime()
    created_before = DateTime()


class SortInput(graphene.InputObjectType):
    """Input for sorting operations."""
    
    field = String(required=True)  # e.g., 'created_at', 'title', 'updated_at'
    direction = String()  # 'ASC' or 'DESC'


# Enum types
class SortDirectionEnum(graphene.Enum):
    """Sort direction enumeration."""
    
    ASC = "ASC"
    DESC = "DESC"


class CategoryEnum(graphene.Enum):
    """Category enumeration."""
    
    GENERAL = "general"
    TECHNICAL = "technical"
    BUSINESS = "business"
    RESEARCH = "research"
    DOCUMENTATION = "documentation"
    TUTORIAL = "tutorial"
    REFERENCE = "reference"


class UserRoleEnum(graphene.Enum):
    """User role enumeration."""
    
    USER = "user"
    ADMIN = "admin"
    MODERATOR = "moderator"


# Union types
class SearchableContent(graphene.Union):
    """Union type for searchable content."""
    
    class Meta:
        types = (KnowledgeEntryType, UserType)


# Interface definitions
class TimestampedInterface(graphene.Interface):
    """Interface for timestamped objects."""
    
    created_at = DateTime()
    updated_at = DateTime()


class AuthoredInterface(graphene.Interface):
    """Interface for authored content."""
    
    author = Field(UserType)
    author_id = Int()


# Custom scalar types
class JSONString(graphene.Scalar):
    """JSON string scalar type."""
    
    @staticmethod
    def serialize(dt):
        """Serialize JSON to string."""
        import json
        return json.dumps(dt)
    
    @staticmethod
    def parse_literal(node):
        """Parse literal JSON."""
        import json
        return json.loads(node.value)
    
    @staticmethod
    def parse_value(value):
        """Parse JSON value."""
        import json
        return json.loads(value)


# Response types
class MutationResponseInterface(graphene.Interface):
    """Interface for mutation responses."""
    
    success = Boolean()
    message = String()
    errors = List(String)


class CreateEntryResponse(ObjectType):
    """Response for create entry mutation."""
    
    class Meta:
        interfaces = (MutationResponseInterface,)
    
    entry = Field(KnowledgeEntryType)


class UpdateEntryResponse(ObjectType):
    """Response for update entry mutation."""
    
    class Meta:
        interfaces = (MutationResponseInterface,)
    
    entry = Field(KnowledgeEntryType)


class DeleteEntryResponse(ObjectType):
    """Response for delete entry mutation."""
    
    class Meta:
        interfaces = (MutationResponseInterface,)
    
    deleted_id = String()


class CreateUserResponse(ObjectType):
    """Response for create user mutation."""
    
    class Meta:
        interfaces = (MutationResponseInterface,)
    
    user = Field(UserType)


class UpdateUserResponse(ObjectType):
    """Response for update user mutation."""
    
    class Meta:
        interfaces = (MutationResponseInterface,)
    
    user = Field(UserType)


# Connection types for pagination
class KnowledgeEntryConnection(relay.Connection):
    """Knowledge Entry connection for pagination."""
    
    class Meta:
        node = KnowledgeEntryType
    
    total_count = Int()
    
    def resolve_total_count(self, info):
        """Resolve total count of entries."""
        return self.length


class UserConnection(relay.Connection):
    """User connection for pagination."""
    
    class Meta:
        node = UserType
    
    total_count = Int()
    
    def resolve_total_count(self, info):
        """Resolve total count of users."""
        return self.length
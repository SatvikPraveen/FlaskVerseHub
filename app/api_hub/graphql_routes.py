# File: app/api_hub/graphql_routes.py
# 🔌 GraphQL Endpoint Implementation

from flask import request, jsonify, current_app
from flask_login import current_user
import graphene
from graphene import relay
from graphene_sqlalchemy import SQLAlchemyObjectType, SQLAlchemyConnectionField
from sqlalchemy import or_, desc

from . import api_hub
from ..models import KnowledgeEntry as KnowledgeEntryModel, User as UserModel, db
from ..security.rate_limiting import rate_limit


# GraphQL Object Types
class User(SQLAlchemyObjectType):
    """GraphQL User type."""
    
    class Meta:
        model = UserModel
        interfaces = (relay.Node, )
        exclude_fields = ('password_hash',)  # Never expose password hash


class KnowledgeEntry(SQLAlchemyObjectType):
    """GraphQL Knowledge Entry type."""
    
    class Meta:
        model = KnowledgeEntryModel
        interfaces = (relay.Node, )
    
    # Add computed fields
    word_count = graphene.Int()
    reading_time = graphene.Int()
    tags_list = graphene.List(graphene.String)
    excerpt = graphene.String()
    
    def resolve_word_count(self, info):
        """Calculate word count of content."""
        return len(self.content.split()) if self.content else 0
    
    def resolve_reading_time(self, info):
        """Estimate reading time in minutes."""
        word_count = self.resolve_word_count(info)
        return max(1, round(word_count / 200))
    
    def resolve_tags_list(self, info):
        """Convert comma-separated tags to list."""
        if self.tags:
            return [tag.strip() for tag in self.tags.split(',') if tag.strip()]
        return []
    
    def resolve_excerpt(self, info):
        """Generate excerpt from content."""
        if self.content:
            import re
            clean_content = re.sub(r'<[^>]+>', '', self.content)
            return clean_content[:200] + '...' if len(clean_content) > 200 else clean_content
        return ''


# Input Types for mutations
class CreateKnowledgeEntryInput(graphene.InputObjectType):
    """Input for creating knowledge entries."""
    title = graphene.String(required=True)
    description = graphene.String()
    content = graphene.String(required=True)
    category = graphene.String(required=True)
    tags = graphene.String()
    source_url = graphene.String()
    is_public = graphene.Boolean()
    is_featured = graphene.Boolean()


class UpdateKnowledgeEntryInput(graphene.InputObjectType):
    """Input for updating knowledge entries."""
    id = graphene.ID(required=True)
    title = graphene.String()
    description = graphene.String()
    content = graphene.String()
    category = graphene.String()
    tags = graphene.String()
    source_url = graphene.String()
    is_public = graphene.Boolean()
    is_featured = graphene.Boolean()


# Query Class
class Query(graphene.ObjectType):
    """GraphQL Query root."""
    
    node = relay.Node.Field()
    
    # Knowledge Entry queries
    all_entries = SQLAlchemyConnectionField(KnowledgeEntry.connection)
    entry = graphene.Field(KnowledgeEntry, id=graphene.ID(required=True))
    search_entries = graphene.List(KnowledgeEntry, query=graphene.String(required=True))
    entries_by_category = graphene.List(KnowledgeEntry, category=graphene.String(required=True))
    
    # User queries
    all_users = SQLAlchemyConnectionField(User.connection)
    user = graphene.Field(User, id=graphene.ID(required=True))
    current_user = graphene.Field(User)
    
    # Statistics
    entry_count = graphene.Int()
    public_entry_count = graphene.Int()
    user_count = graphene.Int()
    
    def resolve_entry(self, info, id):
        """Resolve single entry by ID."""
        entry = KnowledgeEntryModel.query.get(id)
        if not entry:
            return None
        
        # Check permissions
        if not entry.is_public:
            if not current_user.is_authenticated:
                return None
            if entry.author_id != current_user.id and not current_user.is_admin:
                return None
        
        return entry
    
    def resolve_search_entries(self, info, query):
        """Search entries by query."""
        entries_query = KnowledgeEntryModel.query.filter(
            or_(
                KnowledgeEntryModel.title.contains(query),
                KnowledgeEntryModel.content.contains(query),
                KnowledgeEntryModel.tags.contains(query)
            )
        )
        
        # Apply permissions
        if not current_user.is_authenticated:
            entries_query = entries_query.filter_by(is_public=True)
        elif not current_user.is_admin:
            entries_query = entries_query.filter(
                or_(
                    KnowledgeEntryModel.is_public == True,
                    KnowledgeEntryModel.author_id == current_user.id
                )
            )
        
        return entries_query.order_by(desc(KnowledgeEntryModel.created_at)).limit(20).all()
    
    def resolve_entries_by_category(self, info, category):
        """Get entries by category."""
        entries_query = KnowledgeEntryModel.query.filter_by(category=category)
        
        # Apply permissions
        if not current_user.is_authenticated:
            entries_query = entries_query.filter_by(is_public=True)
        elif not current_user.is_admin:
            entries_query = entries_query.filter(
                or_(
                    KnowledgeEntryModel.is_public == True,
                    KnowledgeEntryModel.author_id == current_user.id
                )
            )
        
        return entries_query.order_by(desc(KnowledgeEntryModel.created_at)).all()
    
    def resolve_user(self, info, id):
        """Resolve user by ID."""
        if not current_user.is_authenticated:
            return None
        
        user = UserModel.query.get(id)
        if not user:
            return None
        
        # Users can only see their own profile unless admin
        if current_user.id != user.id and not current_user.is_admin:
            return None
        
        return user
    
    def resolve_current_user(self, info):
        """Get current authenticated user."""
        return current_user if current_user.is_authenticated else None
    
    def resolve_entry_count(self, info):
        """Get total entry count."""
        return KnowledgeEntryModel.query.count()
    
    def resolve_public_entry_count(self, info):
        """Get public entry count."""
        return KnowledgeEntryModel.query.filter_by(is_public=True).count()
    
    def resolve_user_count(self, info):
        """Get total user count."""
        return UserModel.query.count()


# Mutations
class CreateKnowledgeEntry(graphene.Mutation):
    """Create new knowledge entry."""
    
    class Arguments:
        input = CreateKnowledgeEntryInput(required=True)
    
    entry = graphene.Field(KnowledgeEntry)
    success = graphene.Boolean()
    message = graphene.String()
    
    def mutate(self, info, input):
        if not current_user.is_authenticated:
            return CreateKnowledgeEntry(success=False, message="Authentication required")
        
        try:
            entry = KnowledgeEntryModel(
                title=input.title,
                description=input.description or '',
                content=input.content,
                category=input.category,
                tags=input.tags or '',
                source_url=input.source_url,
                is_public=input.is_public or False,
                is_featured=input.is_featured and current_user.is_admin,
                author_id=current_user.id
            )
            
            db.session.add(entry)
            db.session.commit()
            
            return CreateKnowledgeEntry(
                entry=entry,
                success=True,
                message="Entry created successfully"
            )
        
        except Exception as e:
            db.session.rollback()
            return CreateKnowledgeEntry(success=False, message=str(e))


class UpdateKnowledgeEntry(graphene.Mutation):
    """Update knowledge entry."""
    
    class Arguments:
        input = UpdateKnowledgeEntryInput(required=True)
    
    entry = graphene.Field(KnowledgeEntry)
    success = graphene.Boolean()
    message = graphene.String()
    
    def mutate(self, info, input):
        if not current_user.is_authenticated:
            return UpdateKnowledgeEntry(success=False, message="Authentication required")
        
        entry = KnowledgeEntryModel.query.get(input.id)
        if not entry:
            return UpdateKnowledgeEntry(success=False, message="Entry not found")
        
        # Check permissions
        if entry.author_id != current_user.id and not current_user.is_admin:
            return UpdateKnowledgeEntry(success=False, message="Permission denied")
        
        try:
            if input.title is not None:
                entry.title = input.title
            if input.description is not None:
                entry.description = input.description
            if input.content is not None:
                entry.content = input.content
            if input.category is not None:
                entry.category = input.category
            if input.tags is not None:
                entry.tags = input.tags
            if input.source_url is not None:
                entry.source_url = input.source_url
            if input.is_public is not None:
                entry.is_public = input.is_public
            if input.is_featured is not None and current_user.is_admin:
                entry.is_featured = input.is_featured
            
            db.session.commit()
            
            return UpdateKnowledgeEntry(
                entry=entry,
                success=True,
                message="Entry updated successfully"
            )
        
        except Exception as e:
            db.session.rollback()
            return UpdateKnowledgeEntry(success=False, message=str(e))


class DeleteKnowledgeEntry(graphene.Mutation):
    """Delete knowledge entry."""
    
    class Arguments:
        id = graphene.ID(required=True)
    
    success = graphene.Boolean()
    message = graphene.String()
    
    def mutate(self, info, id):
        if not current_user.is_authenticated:
            return DeleteKnowledgeEntry(success=False, message="Authentication required")
        
        entry = KnowledgeEntryModel.query.get(id)
        if not entry:
            return DeleteKnowledgeEntry(success=False, message="Entry not found")
        
        # Check permissions
        if entry.author_id != current_user.id and not current_user.is_admin:
            return DeleteKnowledgeEntry(success=False, message="Permission denied")
        
        try:
            db.session.delete(entry)
            db.session.commit()
            
            return DeleteKnowledgeEntry(
                success=True,
                message="Entry deleted successfully"
            )
        
        except Exception as e:
            db.session.rollback()
            return DeleteKnowledgeEntry(success=False, message=str(e))


class Mutation(graphene.ObjectType):
    """GraphQL Mutation root."""
    
    create_entry = CreateKnowledgeEntry.Field()
    update_entry = UpdateKnowledgeEntry.Field()
    delete_entry = DeleteKnowledgeEntry.Field()


# Create schema
schema = graphene.Schema(query=Query, mutation=Mutation)


# GraphQL endpoint
@api_hub.route('/graphql', methods=['POST'])
@rate_limit('50/hour')
def graphql():
    """GraphQL endpoint."""
    data = request.get_json()
    
    if not data:
        return jsonify({'error': 'No query provided'}), 400
    
    query = data.get('query')
    variables = data.get('variables', {})
    operation_name = data.get('operationName')
    
    if not query:
        return jsonify({'error': 'No query provided'}), 400
    
    try:
        result = schema.execute(
            query,
            variables=variables,
            operation_name=operation_name,
            context={'user': current_user}
        )
        
        response_data = {'data': result.data}
        
        if result.errors:
            response_data['errors'] = [str(error) for error in result.errors]
        
        return jsonify(response_data)
    
    except Exception as e:
        current_app.logger.error(f'GraphQL error: {e}')
        return jsonify({'error': 'Internal server error'}), 500


@api_hub.route('/graphql', methods=['GET'])
def graphql_playground():
    """GraphQL Playground interface."""
    return '''
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset=utf-8/>
        <meta name="viewport" content="user-scalable=no, initial-scale=1.0, minimum-scale=1.0, maximum-scale=1.0, minimal-ui">
        <title>GraphQL Playground</title>
        <link rel="stylesheet" href="//cdn.jsdelivr.net/npm/graphql-playground-react/build/static/css/index.css" />
        <link rel="shortcut icon" href="//cdn.jsdelivr.net/npm/graphql-playground-react/build/favicon.png" />
        <script src="//cdn.jsdelivr.net/npm/graphql-playground-react/build/static/js/middleware.js"></script>
    </head>
    <body>
        <div id="root">
            <style>
                body { margin: 0; font-family: -apple-system,BlinkMacSystemFont,"Segoe UI",Helvetica,Arial,sans-serif,"Apple Color Emoji","Segoe UI Emoji","Segoe UI Symbol"; }
                #root { height: 100vh; }
            </style>
            <div class="loading">Loading...</div>
        </div>
        <script>
            window.addEventListener('load', function (event) {
                GraphQLPlayground.init(document.getElementById('root'), {
                    endpoint: '/api/v1/graphql'
                })
            })
        </script>
    </body>
    </html>
    '''
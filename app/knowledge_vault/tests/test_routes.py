# File: app/knowledge_vault/tests/test_routes.py

import pytest
from flask import url_for
from app.models import KnowledgeEntry, User
from app import db


class TestKnowledgeVaultRoutes:
    """Test cases for Knowledge Vault routes."""
    
    def test_index_route(self, client):
        """Test the main index route."""
        response = client.get(url_for('knowledge_vault.index'))
        assert response.status_code == 200
        assert b'Knowledge Vault' in response.data
    
    def test_index_with_public_entries(self, client, public_entry):
        """Test index displays public entries."""
        response = client.get(url_for('knowledge_vault.index'))
        assert response.status_code == 200
        assert public_entry.title.encode() in response.data
    
    def test_index_hides_private_entries_from_anonymous(self, client, private_entry):
        """Test private entries are hidden from anonymous users."""
        response = client.get(url_for('knowledge_vault.index'))
        assert response.status_code == 200
        assert private_entry.title.encode() not in response.data
    
    def test_index_shows_private_entries_to_owner(self, client, authenticated_user, private_entry):
        """Test private entries are shown to their owners."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(authenticated_user.id)
        
        response = client.get(url_for('knowledge_vault.index'))
        assert response.status_code == 200
        assert private_entry.title.encode() in response.data
    
    def test_search_functionality(self, client, public_entry):
        """Test search functionality."""
        response = client.get(url_for('knowledge_vault.index'), 
                            query_string={'query': public_entry.title[:10]})
        assert response.status_code == 200
        assert public_entry.title.encode() in response.data
    
    def test_category_filter(self, client, public_entry):
        """Test category filtering."""
        response = client.get(url_for('knowledge_vault.index'), 
                            query_string={'category': public_entry.category})
        assert response.status_code == 200
        assert public_entry.title.encode() in response.data
    
    def test_detail_route_public_entry(self, client, public_entry):
        """Test viewing a public entry detail."""
        response = client.get(url_for('knowledge_vault.detail', id=public_entry.id))
        assert response.status_code == 200
        assert public_entry.title.encode() in response.data
        assert public_entry.content.encode() in response.data
    
    def test_detail_route_private_entry_anonymous(self, client, private_entry):
        """Test private entry returns 403 for anonymous users."""
        response = client.get(url_for('knowledge_vault.detail', id=private_entry.id))
        assert response.status_code == 403
    
    def test_detail_route_private_entry_owner(self, client, authenticated_user, private_entry):
        """Test private entry is accessible to owner."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(authenticated_user.id)
        
        response = client.get(url_for('knowledge_vault.detail', id=private_entry.id))
        assert response.status_code == 200
        assert private_entry.title.encode() in response.data
    
    def test_detail_route_nonexistent(self, client):
        """Test 404 for nonexistent entry."""
        response = client.get(url_for('knowledge_vault.detail', id=99999))
        assert response.status_code == 404
    
    def test_create_route_get_authenticated(self, client, authenticated_user):
        """Test GET request to create route for authenticated user."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(authenticated_user.id)
        
        response = client.get(url_for('knowledge_vault.create'))
        assert response.status_code == 200
        assert b'Create New Knowledge Entry' in response.data
    
    def test_create_route_get_anonymous(self, client):
        """Test GET request to create route redirects anonymous users."""
        response = client.get(url_for('knowledge_vault.create'))
        assert response.status_code == 302  # Redirect to login
    
    def test_create_route_post_valid(self, client, authenticated_user):
        """Test POST request to create route with valid data."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(authenticated_user.id)
        
        data = {
            'title': 'Test Entry',
            'description': 'Test description',
            'content': 'Test content for the entry',
            'category': 'general',
            'tags': 'test, example',
            'is_public': True,
            'csrf_token': 'test_token'  # You'll need to mock CSRF
        }
        
        response = client.post(url_for('knowledge_vault.create'), data=data)
        
        # Should redirect to the new entry
        assert response.status_code == 302
        
        # Verify entry was created
        entry = KnowledgeEntry.query.filter_by(title='Test Entry').first()
        assert entry is not None
        assert entry.author_id == authenticated_user.id
    
    def test_create_route_post_invalid(self, client, authenticated_user):
        """Test POST request to create route with invalid data."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(authenticated_user.id)
        
        data = {
            'title': '',  # Empty title should fail validation
            'content': '',  # Empty content should fail validation
            'csrf_token': 'test_token'
        }
        
        response = client.post(url_for('knowledge_vault.create'), data=data)
        assert response.status_code == 200  # Returns form with errors
        assert b'Create New Knowledge Entry' in response.data
    
    def test_edit_route_get_owner(self, client, authenticated_user, private_entry):
        """Test GET request to edit route by entry owner."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(authenticated_user.id)
        
        response = client.get(url_for('knowledge_vault.edit', id=private_entry.id))
        assert response.status_code == 200
        assert b'Edit Knowledge Entry' in response.data
        assert private_entry.title.encode() in response.data
    
    def test_edit_route_get_non_owner(self, client, other_user, private_entry):
        """Test GET request to edit route by non-owner returns 403."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(other_user.id)
        
        response = client.get(url_for('knowledge_vault.edit', id=private_entry.id))
        assert response.status_code == 403
    
    def test_edit_route_post_valid(self, client, authenticated_user, private_entry):
        """Test POST request to edit route with valid data."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(authenticated_user.id)
        
        data = {
            'title': 'Updated Title',
            'description': 'Updated description',
            'content': 'Updated content',
            'category': 'technical',
            'tags': 'updated, test',
            'is_public': True,
            'csrf_token': 'test_token'
        }
        
        response = client.post(url_for('knowledge_vault.edit', id=private_entry.id), data=data)
        assert response.status_code == 302
        
        # Verify entry was updated
        entry = KnowledgeEntry.query.get(private_entry.id)
        assert entry.title == 'Updated Title'
        assert entry.category == 'technical'
    
    def test_delete_route_owner(self, client, authenticated_user, private_entry):
        """Test DELETE request by entry owner."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(authenticated_user.id)
        
        entry_id = private_entry.id
        response = client.post(url_for('knowledge_vault.delete', id=entry_id))
        assert response.status_code == 302
        
        # Verify entry was deleted
        entry = KnowledgeEntry.query.get(entry_id)
        assert entry is None
    
    def test_delete_route_non_owner(self, client, other_user, private_entry):
        """Test DELETE request by non-owner returns 403."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(other_user.id)
        
        response = client.post(url_for('knowledge_vault.delete', id=private_entry.id))
        assert response.status_code == 403
    
    def test_api_entries_route(self, client, public_entry):
        """Test API entries endpoint."""
        response = client.get(url_for('knowledge_vault.api_entries'))
        assert response.status_code == 200
        
        json_data = response.get_json()
        assert 'entries' in json_data
        assert 'pagination' in json_data
        assert len(json_data['entries']) >= 1
    
    def test_categories_route(self, client, public_entry):
        """Test categories endpoint."""
        response = client.get(url_for('knowledge_vault.categories'))
        assert response.status_code == 200
        
        json_data = response.get_json()
        assert 'categories' in json_data
        assert len(json_data['categories']) >= 1
    
    def test_search_suggestions_route(self, client, public_entry):
        """Test search suggestions endpoint."""
        response = client.get(url_for('knowledge_vault.search_suggestions'), 
                            query_string={'q': public_entry.title[:3]})
        assert response.status_code == 200
        
        json_data = response.get_json()
        assert 'suggestions' in json_data
    
    def test_pagination(self, client, app):
        """Test pagination functionality."""
        # Create multiple entries
        user = User(username='testuser', email='test@example.com')
        db.session.add(user)
        db.session.commit()
        
        entries = []
        for i in range(15):
            entry = KnowledgeEntry(
                title=f'Entry {i}',
                content=f'Content for entry {i}',
                category='general',
                author_id=user.id,
                is_public=True
            )
            entries.append(entry)
            db.session.add(entry)
        db.session.commit()
        
        # Test first page
        response = client.get(url_for('knowledge_vault.index'))
        assert response.status_code == 200
        
        # Test second page
        response = client.get(url_for('knowledge_vault.index'), query_string={'page': 2})
        assert response.status_code == 200
    
    def test_bulk_actions_admin_only(self, client, admin_user, public_entry):
        """Test bulk actions are admin-only."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
        
        data = {
            'entry_ids': str(public_entry.id),
            'action': 'make_private',
            'csrf_token': 'test_token'
        }
        
        response = client.post(url_for('knowledge_vault.bulk_actions'), data=data)
        assert response.status_code == 302
        
        # Verify action was applied
        entry = KnowledgeEntry.query.get(public_entry.id)
        assert entry.is_public == False
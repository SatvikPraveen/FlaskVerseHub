# File: app/api_hub/tests/test_rest_api.py

import pytest
import json
from flask import url_for
from app.models import KnowledgeEntry, User


class TestRestAPI:
    """Test REST API endpoints."""
    
    def test_api_login_valid(self, client, user):
        """Test API login with valid credentials."""
        response = client.post('/api/v1/auth/login', 
                              json={
                                  'username': user.username,
                                  'password': 'testpassword123'
                              })
        
        assert response.status_code == 200
        data = response.get_json()
        assert 'access_token' in data
        assert 'refresh_token' in data
        assert data['user']['username'] == user.username
    
    def test_api_login_invalid(self, client, user):
        """Test API login with invalid credentials."""
        response = client.post('/api/v1/auth/login',
                              json={
                                  'username': user.username,
                                  'password': 'wrongpassword'
                              })
        
        assert response.status_code == 401
        data = response.get_json()
        assert 'error' in data
    
    def test_get_entries_public(self, client, public_entry):
        """Test getting public entries."""
        response = client.get('/api/v1/entries')
        
        assert response.status_code == 200
        data = response.get_json()
        assert 'entries' in data
        assert 'pagination' in data
        assert len(data['entries']) >= 1
    
    def test_get_entry_by_id(self, client, public_entry):
        """Test getting specific entry by ID."""
        response = client.get(f'/api/v1/entries/{public_entry.id}')
        
        assert response.status_code == 200
        data = response.get_json()
        assert data['entry']['id'] == public_entry.id
        assert data['entry']['title'] == public_entry.title
    
    def test_create_entry_authenticated(self, client, auth_headers):
        """Test creating entry with authentication."""
        entry_data = {
            'title': 'Test API Entry',
            'content': 'This is test content for API entry',
            'category': 'technical',
            'is_public': True
        }
        
        response = client.post('/api/v1/entries',
                              json=entry_data,
                              headers=auth_headers)
        
        assert response.status_code == 201
        data = response.get_json()
        assert data['entry']['title'] == entry_data['title']
    
    def test_create_entry_unauthenticated(self, client):
        """Test creating entry without authentication."""
        entry_data = {
            'title': 'Test Entry',
            'content': 'Test content',
            'category': 'general'
        }
        
        response = client.post('/api/v1/entries', json=entry_data)
        assert response.status_code == 401
    
    def test_update_entry_owner(self, client, auth_headers, user_entry):
        """Test updating entry by owner."""
        update_data = {
            'title': 'Updated Title',
            'content': 'Updated content'
        }
        
        response = client.put(f'/api/v1/entries/{user_entry.id}',
                             json=update_data,
                             headers=auth_headers)
        
        assert response.status_code == 200
        data = response.get_json()
        assert data['entry']['title'] == update_data['title']
    
    def test_delete_entry_owner(self, client, auth_headers, user_entry):
        """Test deleting entry by owner."""
        response = client.delete(f'/api/v1/entries/{user_entry.id}',
                                headers=auth_headers)
        
        assert response.status_code == 200
        
        # Verify entry is deleted
        entry = KnowledgeEntry.query.get(user_entry.id)
        assert entry is None
    
    def test_search_entries(self, client, public_entry):
        """Test search functionality."""
        response = client.get('/api/v1/search',
                             query_string={'q': public_entry.title[:5]})
        
        assert response.status_code == 200
        data = response.get_json()
        assert 'entries' in data
        assert len(data['entries']) >= 1
    
    def test_get_categories(self, client, public_entry):
        """Test getting categories."""
        response = client.get('/api/v1/categories')
        
        assert response.status_code == 200
        data = response.get_json()
        assert 'categories' in data
        assert len(data['categories']) >= 1
    
    def test_pagination(self, client):
        """Test API pagination."""
        response = client.get('/api/v1/entries', 
                             query_string={'page': 1, 'per_page': 5})
        
        assert response.status_code == 200
        data = response.get_json()
        assert data['pagination']['page'] == 1
        assert data['pagination']['per_page'] == 5
    
    def test_rate_limiting(self, client):
        """Test rate limiting (basic test)."""
        # This would need actual rate limiting implementation
        for _ in range(10):
            response = client.get('/api/v1/entries')
            assert response.status_code == 200
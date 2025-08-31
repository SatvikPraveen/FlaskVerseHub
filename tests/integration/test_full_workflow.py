# File: tests/integration/test_full_workflow.py
# 🧪 End-to-end Testing

import pytest
from flask import url_for
from app.models import User, KnowledgeEntry, db


class TestFullWorkflow:
    """Test complete user workflows."""
    
    def test_user_registration_to_first_entry(self, client):
        """Test complete flow: register -> login -> create entry -> view entry."""
        
        # Step 1: Register new user
        register_data = {
            'username': 'newuser',
            'email': 'newuser@example.com',
            'first_name': 'New',
            'last_name': 'User',
            'password': 'NewPassword123!',
            'confirm_password': 'NewPassword123!',
            'agree_terms': True,
            'csrf_token': 'test'
        }
        
        response = client.post(url_for('auth.register'), 
                              data=register_data, 
                              follow_redirects=True)
        assert response.status_code == 200
        
        # Verify user was created
        user = User.query.filter_by(username='newuser').first()
        assert user is not None
        assert user.email == 'newuser@example.com'
        
        # Step 2: Login
        login_data = {
            'username': 'newuser',
            'password': 'NewPassword123!',
            'csrf_token': 'test'
        }
        
        response = client.post(url_for('auth.login'), 
                              data=login_data, 
                              follow_redirects=True)
        assert response.status_code == 200
        
        # Step 3: Create knowledge entry
        entry_data = {
            'title': 'My First Knowledge Entry',
            'description': 'This is my first entry',
            'content': 'This is the detailed content of my first knowledge entry. It contains useful information.',
            'category': 'general',
            'tags': 'first, test, knowledge',
            'is_public': True,
            'csrf_token': 'test'
        }
        
        response = client.post(url_for('knowledge_vault.create'), 
                              data=entry_data, 
                              follow_redirects=True)
        assert response.status_code == 200
        
        # Verify entry was created
        entry = KnowledgeEntry.query.filter_by(title='My First Knowledge Entry').first()
        assert entry is not None
        assert entry.author_id == user.id
        assert entry.is_public == True
        
        # Step 4: View the entry
        response = client.get(url_for('knowledge_vault.detail', id=entry.id))
        assert response.status_code == 200
        assert b'My First Knowledge Entry' in response.data
        assert b'This is the detailed content' in response.data
        
        # Step 5: Edit the entry
        edit_data = {
            'title': 'My Updated First Entry',
            'description': 'This is my updated first entry',
            'content': 'This is the updated content with more information.',
            'category': 'technical',
            'tags': 'updated, test, knowledge',
            'is_public': True,
            'csrf_token': 'test'
        }
        
        response = client.post(url_for('knowledge_vault.edit', id=entry.id), 
                              data=edit_data, 
                              follow_redirects=True)
        assert response.status_code == 200
        
        # Verify entry was updated
        updated_entry = KnowledgeEntry.query.get(entry.id)
        assert updated_entry.title == 'My Updated First Entry'
        assert updated_entry.category == 'technical'
    
    def test_search_and_filter_workflow(self, client, sample_entries):
        """Test search and filtering functionality."""
        
        # Step 1: Browse all entries
        response = client.get(url_for('knowledge_vault.index'))
        assert response.status_code == 200
        
        # Step 2: Search for specific term
        response = client.get(url_for('knowledge_vault.index'), 
                             query_string={'query': 'Sample'})
        assert response.status_code == 200
        
        # Should find entries with 'Sample' in title
        for entry in sample_entries:
            if 'Sample' in entry.title:
                assert entry.title.encode() in response.data
        
        # Step 3: Filter by category
        response = client.get(url_for('knowledge_vault.index'), 
                             query_string={'category': 'general'})
        assert response.status_code == 200
        
        # Step 4: Combined search and filter
        response = client.get(url_for('knowledge_vault.index'), 
                             query_string={'query': 'Sample', 'category': 'general'})
        assert response.status_code == 200
        
        # Step 5: Test pagination
        response = client.get(url_for('knowledge_vault.index'), 
                             query_string={'page': 1})
        assert response.status_code == 200
    
    def test_admin_workflow(self, client, admin_user, user_entry):
        """Test admin-specific workflows."""
        
        # Step 1: Login as admin
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
        
        # Step 2: Access admin features
        response = client.get(url_for('dashboard.analytics'))
        assert response.status_code == 200
        
        # Step 3: Edit another user's entry
        edit_data = {
            'title': 'Admin Updated Entry',
            'description': 'Updated by admin',
            'content': 'This entry was updated by an administrator.',
            'category': 'general',
            'is_featured': True,
            'csrf_token': 'test'
        }
        
        response = client.post(url_for('knowledge_vault.edit', id=user_entry.id), 
                              data=edit_data, 
                              follow_redirects=True)
        assert response.status_code == 200
        
        # Verify admin could edit entry
        updated_entry = KnowledgeEntry.query.get(user_entry.id)
        assert updated_entry.title == 'Admin Updated Entry'
        assert updated_entry.is_featured == True
        
        # Step 4: Perform bulk operations
        bulk_data = {
            'entry_ids': str(user_entry.id),
            'action': 'make_public',
            'csrf_token': 'test'
        }
        
        response = client.post(url_for('knowledge_vault.bulk_actions'), 
                              data=bulk_data, 
                              follow_redirects=True)
        assert response.status_code == 200
    
    def test_error_handling_workflow(self, client, user):
        """Test error handling in various scenarios."""
        
        # Login user
        with client.session_transaction() as sess:
            sess['_user_id'] = str(user.id)
        
        # Step 1: Try to access non-existent entry
        response = client.get(url_for('knowledge_vault.detail', id=99999))
        assert response.status_code == 404
        
        # Step 2: Try to edit non-existent entry
        response = client.get(url_for('knowledge_vault.edit', id=99999))
        assert response.status_code == 404
        
        # Step 3: Try to create entry with invalid data
        invalid_data = {
            'title': '',  # Empty title
            'content': '',  # Empty content
            'category': 'invalid_category',
            'csrf_token': 'test'
        }
        
        response = client.post(url_for('knowledge_vault.create'), 
                              data=invalid_data)
        assert response.status_code == 200  # Form validation errors
        
        # Step 4: Try to access admin-only features as regular user
        response = client.get(url_for('dashboard.analytics'))
        assert response.status_code == 403
    
    def test_profile_management_workflow(self, client, user):
        """Test profile management workflow."""
        
        # Login user
        with client.session_transaction() as sess:
            sess['_user_id'] = str(user.id)
        
        # Step 1: View profile
        response = client.get(url_for('auth.profile'))
        assert response.status_code == 200
        assert user.username.encode() in response.data
        
        # Step 2: Update profile
        profile_data = {
            'username': user.username,
            'email': user.email,
            'first_name': 'Updated',
            'last_name': 'Name',
            'bio': 'This is my updated bio.',
            'csrf_token': 'test'
        }
        
        response = client.post(url_for('auth.profile'), 
                              data=profile_data, 
                              follow_redirects=True)
        assert response.status_code == 200
        
        # Verify profile was updated
        updated_user = User.query.get(user.id)
        assert updated_user.first_name == 'Updated'
        assert updated_user.last_name == 'Name'
        assert updated_user.bio == 'This is my updated bio.'
        
        # Step 3: Change password
        password_data = {
            'current_password': 'testpassword123',
            'new_password': 'NewPassword456!',
            'confirm_password': 'NewPassword456!',
            'csrf_token': 'test'
        }
        
        response = client.post(url_for('auth.change_password'), 
                              data=password_data, 
                              follow_redirects=True)
        assert response.status_code == 200
        
        # Verify password was changed
        assert updated_user.check_password('NewPassword456!')
        assert not updated_user.check_password('testpassword123')
    
    def test_api_workflow(self, client, user):
        """Test API workflow end-to-end."""
        
        # Step 1: Login via API
        login_data = {
            'username': user.username,
            'password': 'testpassword123'
        }
        
        response = client.post('/api/v1/auth/login', json=login_data)
        assert response.status_code == 200
        
        data = response.get_json()
        access_token = data['access_token']
        
        # Step 2: Create entry via API
        headers = {'Authorization': f'Bearer {access_token}'}
        entry_data = {
            'title': 'API Created Entry',
            'content': 'This entry was created via the REST API.',
            'category': 'technical',
            'is_public': True
        }
        
        response = client.post('/api/v1/entries', 
                              json=entry_data, 
                              headers=headers)
        assert response.status_code == 201
        
        entry_response = response.get_json()
        entry_id = entry_response['entry']['id']
        
        # Step 3: Get entry via API
        response = client.get(f'/api/v1/entries/{entry_id}', headers=headers)
        assert response.status_code == 200
        
        # Step 4: Update entry via API
        update_data = {
            'title': 'Updated API Entry',
            'content': 'This entry was updated via the REST API.'
        }
        
        response = client.put(f'/api/v1/entries/{entry_id}', 
                             json=update_data, 
                             headers=headers)
        assert response.status_code == 200
        
        # Step 5: Search via API
        response = client.get('/api/v1/search?q=API', headers=headers)
        assert response.status_code == 200
        
        search_results = response.get_json()
        assert len(search_results['entries']) >= 1
        
        # Step 6: Delete entry via API
        response = client.delete(f'/api/v1/entries/{entry_id}', headers=headers)
        assert response.status_code == 200
        
        # Verify entry was deleted
        response = client.get(f'/api/v1/entries/{entry_id}')
        assert response.status_code == 404
# File: app/auth/tests/test_auth_routes.py

import pytest
from flask import url_for
from app.models import User
from app import db


class TestAuthRoutes:
    """Test authentication routes."""
    
    def test_login_get(self, client):
        """Test login page loads."""
        response = client.get(url_for('auth.login'))
        assert response.status_code == 200
        assert b'Sign In' in response.data
    
    def test_login_post_valid(self, client, user):
        """Test valid login."""
        response = client.post(url_for('auth.login'), data={
            'username': user.username,
            'password': 'testpassword123',
            'csrf_token': 'test'
        }, follow_redirects=True)
        assert response.status_code == 200
    
    def test_login_post_invalid(self, client, user):
        """Test invalid login."""
        response = client.post(url_for('auth.login'), data={
            'username': user.username,
            'password': 'wrongpassword',
            'csrf_token': 'test'
        })
        assert response.status_code == 200
        assert b'Invalid username' in response.data
    
    def test_register_get(self, client):
        """Test register page loads."""
        response = client.get(url_for('auth.register'))
        assert response.status_code == 200
        assert b'Create Account' in response.data
    
    def test_register_post_valid(self, client):
        """Test valid registration."""
        response = client.post(url_for('auth.register'), data={
            'username': 'newuser',
            'email': 'new@example.com',
            'password': 'NewPassword123!',
            'confirm_password': 'NewPassword123!',
            'agree_terms': True,
            'csrf_token': 'test'
        }, follow_redirects=True)
        assert response.status_code == 200
        
        user = User.query.filter_by(username='newuser').first()
        assert user is not None
    
    def test_register_duplicate_username(self, client, user):
        """Test registration with duplicate username."""
        response = client.post(url_for('auth.register'), data={
            'username': user.username,
            'email': 'different@example.com',
            'password': 'NewPassword123!',
            'confirm_password': 'NewPassword123!',
            'agree_terms': True,
            'csrf_token': 'test'
        })
        assert response.status_code == 200
        assert b'already taken' in response.data
    
    def test_logout(self, client, authenticated_user):
        """Test logout."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(authenticated_user.id)
        
        response = client.get(url_for('auth.logout'), follow_redirects=True)
        assert response.status_code == 200
    
    def test_profile_requires_auth(self, client):
        """Test profile requires authentication."""
        response = client.get(url_for('auth.profile'))
        assert response.status_code == 302
    
    def test_profile_authenticated(self, client, authenticated_user):
        """Test profile page for authenticated user."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(authenticated_user.id)
        
        response = client.get(url_for('auth.profile'))
        assert response.status_code == 200
        assert authenticated_user.username.encode() in response.data
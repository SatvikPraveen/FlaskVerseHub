# File: app/auth/tests/test_decorators.py

import pytest
from flask import jsonify
from app.auth.decorators import login_required, role_required, admin_required
from app.models import User


def test_login_required_unauthenticated(client, app):
    """Test login_required decorator with unauthenticated user."""
    
    @app.route('/test-login-required')
    @login_required
    def test_route():
        return 'Success'
    
    response = client.get('/test-login-required')
    assert response.status_code == 401


def test_login_required_authenticated(client, app, authenticated_user):
    """Test login_required decorator with authenticated user."""
    
    @app.route('/test-login-required')
    @login_required
    def test_route():
        return 'Success'
    
    with client.session_transaction() as sess:
        sess['_user_id'] = str(authenticated_user.id)
    
    response = client.get('/test-login-required')
    assert response.status_code == 200
    assert b'Success' in response.data


def test_admin_required_non_admin(client, app, authenticated_user):
    """Test admin_required decorator with non-admin user."""
    
    @app.route('/test-admin-required')
    @admin_required
    def test_route():
        return 'Admin Success'
    
    with client.session_transaction() as sess:
        sess['_user_id'] = str(authenticated_user.id)
    
    response = client.get('/test-admin-required')
    assert response.status_code == 403


def test_admin_required_admin_user(client, app, admin_user):
    """Test admin_required decorator with admin user."""
    
    @app.route('/test-admin-required')
    @admin_required
    def test_route():
        return 'Admin Success'
    
    with client.session_transaction() as sess:
        sess['_user_id'] = str(admin_user.id)
    
    response = client.get('/test-admin-required')
    assert response.status_code == 200
    assert b'Admin Success' in response.data


def test_role_required_decorator(client, app, authenticated_user):
    """Test role_required decorator."""
    
    @app.route('/test-role-required')
    @role_required('admin', 'moderator')
    def test_route():
        return 'Role Success'
    
    with client.session_transaction() as sess:
        sess['_user_id'] = str(authenticated_user.id)
    
    # Non-admin user should be forbidden
    response = client.get('/test-role-required')
    assert response.status_code == 403
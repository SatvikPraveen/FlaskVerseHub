# File: tests/conftest.py
# 🧪 Pytest Fixtures and Configuration

import pytest
import tempfile
import os
from app import create_app, db
from app.models import User, KnowledgeEntry
from app.auth.jwt_utils import create_access_token


@pytest.fixture
def app():
    """Create application for testing."""
    db_fd, db_path = tempfile.mkstemp()
    
    app = create_app('testing')
    app.config['DATABASE'] = db_path
    app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{db_path}'
    app.config['WTF_CSRF_ENABLED'] = False
    
    with app.app_context():
        db.create_all()
        yield app
        db.drop_all()
    
    os.close(db_fd)
    os.unlink(db_path)


@pytest.fixture
def client(app):
    """Create test client."""
    return app.test_client()


@pytest.fixture
def runner(app):
    """Create test CLI runner."""
    return app.test_cli_runner()


@pytest.fixture
def user(app):
    """Create test user."""
    user = User(
        username='testuser',
        email='test@example.com',
        first_name='Test',
        last_name='User',
        is_active=True
    )
    user.set_password('testpassword123')
    
    db.session.add(user)
    db.session.commit()
    return user


@pytest.fixture
def admin_user(app):
    """Create admin user."""
    admin = User(
        username='admin',
        email='admin@example.com',
        first_name='Admin',
        last_name='User',
        is_admin=True,
        is_active=True
    )
    admin.set_password('adminpassword123')
    
    db.session.add(admin)
    db.session.commit()
    return admin


@pytest.fixture
def authenticated_user(client, user):
    """Authenticate user for session."""
    with client.session_transaction() as sess:
        sess['_user_id'] = str(user.id)
        sess['_fresh'] = True
    return user


@pytest.fixture
def public_entry(app, user):
    """Create public knowledge entry."""
    entry = KnowledgeEntry(
        title='Public Test Entry',
        description='A test entry that is public',
        content='This is the content of a public test entry. It contains useful information.',
        category='general',
        tags='test, public, example',
        is_public=True,
        author_id=user.id
    )
    
    db.session.add(entry)
    db.session.commit()
    return entry


@pytest.fixture
def private_entry(app, user):
    """Create private knowledge entry."""
    entry = KnowledgeEntry(
        title='Private Test Entry',
        description='A test entry that is private',
        content='This is the content of a private test entry. Only the author can see it.',
        category='technical',
        tags='test, private',
        is_public=False,
        author_id=user.id
    )
    
    db.session.add(entry)
    db.session.commit()
    return entry


@pytest.fixture
def user_entry(app, user):
    """Create entry owned by user."""
    entry = KnowledgeEntry(
        title='User Test Entry',
        description='Entry owned by test user',
        content='This entry is owned by the test user for testing purposes.',
        category='documentation',
        tags='user, test',
        is_public=True,
        author_id=user.id
    )
    
    db.session.add(entry)
    db.session.commit()
    return entry


@pytest.fixture
def other_user(app):
    """Create another test user."""
    user = User(
        username='otheruser',
        email='other@example.com',
        first_name='Other',
        last_name='User',
        is_active=True
    )
    user.set_password('otherpassword123')
    
    db.session.add(user)
    db.session.commit()
    return user


@pytest.fixture
def auth_token(user):
    """Create JWT authentication token."""
    return create_access_token(user)


@pytest.fixture
def auth_headers(auth_token):
    """Create authentication headers."""
    return {'Authorization': f'Bearer {auth_token}'}


@pytest.fixture
def sample_entries(app, user, other_user):
    """Create multiple sample entries."""
    entries = []
    
    # Create entries for different scenarios
    for i in range(5):
        entry = KnowledgeEntry(
            title=f'Sample Entry {i+1}',
            description=f'Sample description {i+1}',
            content=f'Sample content for entry {i+1}. This contains test data.',
            category='general' if i % 2 == 0 else 'technical',
            tags=f'sample, test, entry{i+1}',
            is_public=True,
            author_id=user.id if i < 3 else other_user.id
        )
        entries.append(entry)
        db.session.add(entry)
    
    db.session.commit()
    return entries


@pytest.fixture
def mock_mail(app, monkeypatch):
    """Mock email sending."""
    sent_mails = []
    
    def mock_send(self, message):
        sent_mails.append(message)
    
    from flask_mail import Mail
    monkeypatch.setattr(Mail, 'send', mock_send)
    
    return sent_mails


@pytest.fixture
def mock_socketio(monkeypatch):
    """Mock SocketIO emissions."""
    emitted_events = []
    
    def mock_emit(event, data=None, room=None, namespace=None):
        emitted_events.append({
            'event': event,
            'data': data,
            'room': room,
            'namespace': namespace
        })
    
    from app.extensions import socketio
    monkeypatch.setattr(socketio, 'emit', mock_emit)
    
    return emitted_events
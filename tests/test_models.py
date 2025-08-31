# File: tests/test_models.py
# 🧪 Model Testing

import pytest
from datetime import datetime
from app.models import User, KnowledgeEntry, db


class TestUserModel:
    """Test User model."""
    
    def test_user_creation(self, app):
        """Test user creation."""
        user = User(
            username='testuser',
            email='test@example.com',
            first_name='Test',
            last_name='User'
        )
        user.set_password('testpassword')
        
        db.session.add(user)
        db.session.commit()
        
        assert user.id is not None
        assert user.username == 'testuser'
        assert user.email == 'test@example.com'
        assert user.created_at is not None
        assert user.is_active == True
        assert user.is_admin == False
    
    def test_password_hashing(self, app):
        """Test password hashing and verification."""
        user = User(username='test', email='test@example.com')
        password = 'testpassword123'
        
        user.set_password(password)
        
        # Password should be hashed
        assert user.password_hash != password
        assert user.password_hash is not None
        
        # Should verify correct password
        assert user.check_password(password) == True
        
        # Should reject wrong password
        assert user.check_password('wrongpassword') == False
    
    def test_user_full_name(self, app):
        """Test full name property."""
        # User with first and last name
        user1 = User(
            username='test1',
            email='test1@example.com',
            first_name='John',
            last_name='Doe'
        )
        assert user1.full_name == 'John Doe'
        
        # User without names should return username
        user2 = User(username='test2', email='test2@example.com')
        assert user2.full_name == 'test2'
    
    def test_user_repr(self, app):
        """Test user string representation."""
        user = User(username='testuser', email='test@example.com')
        assert repr(user) == '<User testuser>'
    
    def test_user_entries_relationship(self, app, user):
        """Test user-entries relationship."""
        # Create entries for the user
        entry1 = KnowledgeEntry(
            title='Entry 1',
            content='Content 1',
            category='general',
            author_id=user.id
        )
        entry2 = KnowledgeEntry(
            title='Entry 2',
            content='Content 2',
            category='technical',
            author_id=user.id
        )
        
        db.session.add_all([entry1, entry2])
        db.session.commit()
        
        # Test relationship
        assert user.knowledge_entries.count() == 2
        assert entry1 in user.knowledge_entries.all()
        assert entry2 in user.knowledge_entries.all()


class TestKnowledgeEntryModel:
    """Test KnowledgeEntry model."""
    
    def test_entry_creation(self, app, user):
        """Test knowledge entry creation."""
        entry = KnowledgeEntry(
            title='Test Entry',
            description='Test description',
            content='This is test content',
            category='general',
            tags='test, example',
            author_id=user.id
        )
        
        db.session.add(entry)
        db.session.commit()
        
        assert entry.id is not None
        assert entry.title == 'Test Entry'
        assert entry.content == 'This is test content'
        assert entry.category == 'general'
        assert entry.created_at is not None
        assert entry.is_public == False  # Default
        assert entry.is_featured == False  # Default
        assert entry.author_id == user.id
    
    def test_entry_word_count(self, app, user):
        """Test word count calculation."""
        entry = KnowledgeEntry(
            title='Test Entry',
            content='This is a test content with exactly eight words',
            category='general',
            author_id=user.id
        )
        
        assert entry.word_count == 8
        
        # Test with empty content
        entry.content = ''
        assert entry.word_count == 0
        
        # Test with None content
        entry.content = None
        assert entry.word_count == 0
    
    def test_entry_reading_time(self, app, user):
        """Test reading time calculation."""
        # Short content (less than 200 words)
        short_content = ' '.join(['word'] * 100)
        entry = KnowledgeEntry(
            title='Short Entry',
            content=short_content,
            category='general',
            author_id=user.id
        )
        
        assert entry.reading_time == 1  # Minimum 1 minute
        
        # Longer content
        long_content = ' '.join(['word'] * 400)
        entry.content = long_content
        
        assert entry.reading_time == 2  # 400 words / 200 = 2 minutes
    
    def test_entry_tags_list(self, app, user):
        """Test tags list property."""
        entry = KnowledgeEntry(
            title='Test Entry',
            content='Test content',
            category='general',
            tags='python, flask, web-development',
            author_id=user.id
        )
        
        expected_tags = ['python', 'flask', 'web-development']
        assert entry.tags_list == expected_tags
        
        # Test with empty tags
        entry.tags = ''
        assert entry.tags_list == []
        
        # Test with None tags
        entry.tags = None
        assert entry.tags_list == []
        
        # Test with tags having extra spaces
        entry.tags = ' python , flask , web-development '
        assert entry.tags_list == ['python', 'flask', 'web-development']
    
    def test_entry_repr(self, app, user):
        """Test entry string representation."""
        entry = KnowledgeEntry(
            title='Test Entry',
            content='Test content',
            category='general',
            author_id=user.id
        )
        
        assert repr(entry) == '<KnowledgeEntry Test Entry>'
    
    def test_entry_author_relationship(self, app, user):
        """Test entry-author relationship."""
        entry = KnowledgeEntry(
            title='Test Entry',
            content='Test content',
            category='general',
            author_id=user.id
        )
        
        db.session.add(entry)
        db.session.commit()
        
        # Test relationship
        assert entry.author == user
        assert entry.author.username == user.username
    
    def test_entry_timestamps(self, app, user):
        """Test entry timestamp behavior."""
        entry = KnowledgeEntry(
            title='Test Entry',
            content='Test content',
            category='general',
            author_id=user.id
        )
        
        # Before saving
        assert entry.created_at is None
        assert entry.updated_at is None
        
        db.session.add(entry)
        db.session.commit()
        
        # After saving
        assert entry.created_at is not None
        assert entry.updated_at is not None
        assert isinstance(entry.created_at, datetime)
        assert isinstance(entry.updated_at, datetime)
        
        # Store original timestamps
        original_created = entry.created_at
        original_updated = entry.updated_at
        
        # Update entry
        entry.title = 'Updated Title'
        db.session.commit()
        
        # created_at should not change, updated_at should change
        assert entry.created_at == original_created
        assert entry.updated_at > original_updated
    
    def test_entry_public_private(self, app, user):
        """Test public/private entry behavior."""
        # Create private entry
        private_entry = KnowledgeEntry(
            title='Private Entry',
            content='Private content',
            category='general',
            is_public=False,
            author_id=user.id
        )
        
        # Create public entry
        public_entry = KnowledgeEntry(
            title='Public Entry',
            content='Public content',
            category='general',
            is_public=True,
            author_id=user.id
        )
        
        db.session.add_all([private_entry, public_entry])
        db.session.commit()
        
        # Test queries
        public_entries = KnowledgeEntry.query.filter_by(is_public=True).all()
        private_entries = KnowledgeEntry.query.filter_by(is_public=False).all()
        
        assert public_entry in public_entries
        assert private_entry not in public_entries
        assert private_entry in private_entries
        assert public_entry not in private_entries
    
    def test_entry_cascade_delete(self, app):
        """Test cascade delete behavior."""
        # Create user and entry
        user = User(username='testuser', email='test@example.com')
        user.set_password('password')
        db.session.add(user)
        db.session.commit()
        
        entry = KnowledgeEntry(
            title='Test Entry',
            content='Test content',
            category='general',
            author_id=user.id
        )
        db.session.add(entry)
        db.session.commit()
        
        entry_id = entry.id
        
        # Delete user should cascade delete entries
        db.session.delete(user)
        db.session.commit()
        
        # Entry should be deleted
        deleted_entry = KnowledgeEntry.query.get(entry_id)
        assert deleted_entry is None
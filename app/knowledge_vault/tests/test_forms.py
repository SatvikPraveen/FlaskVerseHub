# File: app/knowledge_vault/tests/test_forms.py

import pytest
from app.knowledge_vault.forms import KnowledgeEntryForm, SearchForm, BulkDeleteForm


class TestKnowledgeEntryForm:
    """Test cases for KnowledgeEntryForm."""
    
    def test_valid_form(self):
        """Test form with valid data."""
        form = KnowledgeEntryForm(data={
            'title': 'Test Entry',
            'description': 'Test description',
            'content': 'This is test content for the entry',
            'category': 'general',
            'tags': 'test, example',
            'source_url': 'https://example.com',
            'is_public': True,
            'is_featured': False
        })
        
        assert form.validate() == True
    
    def test_empty_title(self):
        """Test form validation with empty title."""
        form = KnowledgeEntryForm(data={
            'title': '',
            'content': 'This is test content',
            'category': 'general'
        })
        
        assert form.validate() == False
        assert 'Title is required' in form.title.errors
    
    def test_empty_content(self):
        """Test form validation with empty content."""
        form = KnowledgeEntryForm(data={
            'title': 'Test Entry',
            'content': '',
            'category': 'general'
        })
        
        assert form.validate() == False
        assert 'Content is required' in form.content.errors
    
    def test_short_content(self):
        """Test form validation with content too short."""
        form = KnowledgeEntryForm(data={
            'title': 'Test Entry',
            'content': 'Short',
            'category': 'general'
        })
        
        assert form.validate() == False
        assert 'Content must be at least 10 characters long' in form.content.errors
    
    def test_title_too_long(self):
        """Test form validation with title too long."""
        long_title = 'x' * 201
        form = KnowledgeEntryForm(data={
            'title': long_title,
            'content': 'This is test content for the entry',
            'category': 'general'
        })
        
        assert form.validate() == False
        assert 'Title must be between 3 and 200 characters' in form.title.errors
    
    def test_title_too_short(self):
        """Test form validation with title too short."""
        form = KnowledgeEntryForm(data={
            'title': 'Te',
            'content': 'This is test content for the entry',
            'category': 'general'
        })
        
        assert form.validate() == False
        assert 'Title must be between 3 and 200 characters' in form.title.errors
    
    def test_invalid_url(self):
        """Test form validation with invalid URL."""
        form = KnowledgeEntryForm(data={
            'title': 'Test Entry',
            'content': 'This is test content for the entry',
            'category': 'general',
            'source_url': 'not-a-url'
        })
        
        assert form.validate() == False
        assert 'Please enter a valid URL' in form.source_url.errors
    
    def test_description_too_long(self):
        """Test form validation with description too long."""
        long_description = 'x' * 501
        form = KnowledgeEntryForm(data={
            'title': 'Test Entry',
            'content': 'This is test content for the entry',
            'category': 'general',
            'description': long_description
        })
        
        assert form.validate() == False
        assert 'Description cannot exceed 500 characters' in form.description.errors
    
    def test_tags_too_long(self):
        """Test form validation with tags too long."""
        long_tags = 'x' * 201
        form = KnowledgeEntryForm(data={
            'title': 'Test Entry',
            'content': 'This is test content for the entry',
            'category': 'general',
            'tags': long_tags
        })
        
        assert form.validate() == False
        assert 'Tags cannot exceed 200 characters' in form.tags.errors
    
    def test_no_category_selected(self):
        """Test form validation with no category selected."""
        form = KnowledgeEntryForm(data={
            'title': 'Test Entry',
            'content': 'This is test content for the entry',
            'category': ''
        })
        
        assert form.validate() == False
        assert 'Please select a category' in form.category.errors
    
    def test_optional_fields(self):
        """Test form with only required fields."""
        form = KnowledgeEntryForm(data={
            'title': 'Test Entry',
            'content': 'This is test content for the entry',
            'category': 'general'
        })
        
        assert form.validate() == True
    
    def test_boolean_fields_default(self):
        """Test boolean fields have correct default values."""
        form = KnowledgeEntryForm()
        assert form.is_public.data == False
        assert form.is_featured.data == False


class TestSearchForm:
    """Test cases for SearchForm."""
    
    def test_valid_search_form(self):
        """Test search form with valid data."""
        form = SearchForm(data={
            'query': 'test search',
            'category': 'general'
        })
        
        assert form.validate() == True
    
    def test_empty_query(self):
        """Test search form with empty query."""
        form = SearchForm(data={
            'query': '',
            'category': 'general'
        })
        
        assert form.validate() == False
        assert 'Search query is required' in form.query.errors
    
    def test_query_too_long(self):
        """Test search form with query too long."""
        long_query = 'x' * 101
        form = SearchForm(data={
            'query': long_query,
            'category': 'general'
        })
        
        assert form.validate() == False
        assert 'Search query must be between 1 and 100 characters' in form.query.errors
    
    def test_category_optional(self):
        """Test search form with no category selected."""
        form = SearchForm(data={
            'query': 'test search',
            'category': ''
        })
        
        assert form.validate() == True
    
    def test_whitespace_only_query(self):
        """Test search form with whitespace-only query."""
        form = SearchForm(data={
            'query': '   ',
            'category': 'general'
        })
        
        # The form should handle this properly
        # Depending on your validation logic, this might pass or fail
        # Adjust based on your actual implementation


class TestBulkDeleteForm:
    """Test cases for BulkDeleteForm."""
    
    def test_valid_bulk_form(self):
        """Test bulk delete form with valid data."""
        form = BulkDeleteForm(data={
            'entry_ids': '1,2,3',
            'action': 'delete'
        })
        
        assert form.validate() == True
    
    def test_empty_entry_ids(self):
        """Test bulk form with empty entry IDs."""
        form = BulkDeleteForm(data={
            'entry_ids': '',
            'action': 'delete'
        })
        
        assert form.validate() == False
        assert 'Entry IDs are required' in form.entry_ids.errors
    
    def test_no_action_selected(self):
        """Test bulk form with no action selected."""
        form = BulkDeleteForm(data={
            'entry_ids': '1,2,3',
            'action': ''
        })
        
        assert form.validate() == False
        assert 'Please select an action' in form.action.errors
    
    def test_all_actions_valid(self):
        """Test all available actions are valid."""
        valid_actions = ['delete', 'archive', 'unarchive', 'make_public', 'make_private']
        
        for action in valid_actions:
            form = BulkDeleteForm(data={
                'entry_ids': '1,2,3',
                'action': action
            })
            assert form.validate() == True, f"Action '{action}' should be valid"


class TestFormFieldChoices:
    """Test form field choices are properly set."""
    
    def test_category_choices(self):
        """Test category field has all expected choices."""
        form = KnowledgeEntryForm()
        expected_categories = [
            ('general', 'General'),
            ('technical', 'Technical'),
            ('business', 'Business'),
            ('research', 'Research'),
            ('documentation', 'Documentation'),
            ('tutorial', 'Tutorial'),
            ('reference', 'Reference')
        ]
        
        assert form.category.choices == expected_categories
    
    def test_search_category_choices(self):
        """Test search form category choices include 'All Categories'."""
        form = SearchForm()
        expected_first_choice = ('', 'All Categories')
        
        assert form.category.choices[0] == expected_first_choice
    
    def test_bulk_action_choices(self):
        """Test bulk action form has all expected choices."""
        form = BulkDeleteForm()
        expected_actions = [
            ('delete', 'Delete'),
            ('archive', 'Archive'),
            ('unarchive', 'Unarchive'),
            ('make_public', 'Make Public'),
            ('make_private', 'Make Private')
        ]
        
        assert form.action.choices == expected_actions


class TestFormRenderingAttributes:
    """Test form fields have correct rendering attributes."""
    
    def test_title_field_attributes(self):
        """Test title field has correct attributes."""
        form = KnowledgeEntryForm()
        assert 'placeholder' in form.title.render_kw
        assert form.title.render_kw['placeholder'] == 'Enter knowledge entry title'
    
    def test_content_field_attributes(self):
        """Test content field has correct attributes."""
        form = KnowledgeEntryForm()
        assert 'rows' in form.content.render_kw
        assert form.content.render_kw['rows'] == 15
    
    def test_description_field_attributes(self):
        """Test description field has correct attributes."""
        form = KnowledgeEntryForm()
        assert 'rows' in form.description.render_kw
        assert form.description.render_kw['rows'] == 3
    
    def test_search_input_attributes(self):
        """Test search input has correct attributes."""
        form = SearchForm()
        assert 'class' in form.query.render_kw
        assert 'form-control' in form.query.render_kw['class']
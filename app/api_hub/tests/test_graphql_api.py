# File: app/api_hub/tests/test_graphql_api.py

import pytest
import json
from app.models import KnowledgeEntry


class TestGraphQLAPI:
    """Test GraphQL API endpoints."""
    
    def test_graphql_query_entries(self, client, public_entry):
        """Test GraphQL query for entries."""
        query = """
        query {
            allEntries(first: 10) {
                edges {
                    node {
                        id
                        title
                        content
                        category
                        isPublic
                        author {
                            username
                        }
                    }
                }
            }
        }
        """
        
        response = client.post('/api/v1/graphql',
                              json={'query': query})
        
        assert response.status_code == 200
        data = response.get_json()
        assert 'data' in data
        assert 'allEntries' in data['data']
    
    def test_graphql_query_single_entry(self, client, public_entry):
        """Test GraphQL query for single entry."""
        query = f"""
        query {{
            entry(id: "{public_entry.id}") {{
                id
                title
                content
                wordCount
                readingTime
                tagsList
                author {{
                    username
                }}
            }}
        }}
        """
        
        response = client.post('/api/v1/graphql',
                              json={'query': query})
        
        assert response.status_code == 200
        data = response.get_json()
        assert data['data']['entry']['title'] == public_entry.title
    
    def test_graphql_search_entries(self, client, public_entry):
        """Test GraphQL search functionality."""
        query = f"""
        query {{
            searchEntries(query: "{public_entry.title[:5]}") {{
                id
                title
                excerpt
            }}
        }}
        """
        
        response = client.post('/api/v1/graphql',
                              json={'query': query})
        
        assert response.status_code == 200
        data = response.get_json()
        assert len(data['data']['searchEntries']) >= 1
    
    def test_graphql_create_entry_mutation(self, client, auth_headers):
        """Test GraphQL mutation for creating entry."""
        mutation = """
        mutation {
            createEntry(input: {
                title: "GraphQL Test Entry"
                content: "This is test content created via GraphQL"
                category: "technical"
                isPublic: true
            }) {
                entry {
                    id
                    title
                    content
                    category
                }
                success
                message
            }
        }
        """
        
        response = client.post('/api/v1/graphql',
                              json={'query': mutation},
                              headers=auth_headers)
        
        assert response.status_code == 200
        data = response.get_json()
        assert data['data']['createEntry']['success'] == True
        assert data['data']['createEntry']['entry']['title'] == "GraphQL Test Entry"
    
    def test_graphql_update_entry_mutation(self, client, auth_headers, user_entry):
        """Test GraphQL mutation for updating entry."""
        mutation = f"""
        mutation {{
            updateEntry(input: {{
                id: "{user_entry.id}"
                title: "Updated via GraphQL"
                content: "Updated content"
            }}) {{
                entry {{
                    id
                    title
                    content
                }}
                success
                message
            }}
        }}
        """
        
        response = client.post('/api/v1/graphql',
                              json={'query': mutation},
                              headers=auth_headers)
        
        assert response.status_code == 200
        data = response.get_json()
        assert data['data']['updateEntry']['success'] == True
        assert data['data']['updateEntry']['entry']['title'] == "Updated via GraphQL"
    
    def test_graphql_delete_entry_mutation(self, client, auth_headers, user_entry):
        """Test GraphQL mutation for deleting entry."""
        mutation = f"""
        mutation {{
            deleteEntry(id: "{user_entry.id}") {{
                success
                message
            }}
        }}
        """
        
        response = client.post('/api/v1/graphql',
                              json={'query': mutation},
                              headers=auth_headers)
        
        assert response.status_code == 200
        data = response.get_json()
        assert data['data']['deleteEntry']['success'] == True
        
        # Verify entry is deleted
        entry = KnowledgeEntry.query.get(user_entry.id)
        assert entry is None
    
    def test_graphql_statistics(self, client):
        """Test GraphQL statistics query."""
        query = """
        query {
            entryCount
            publicEntryCount
            userCount
        }
        """
        
        response = client.post('/api/v1/graphql',
                              json={'query': query})
        
        assert response.status_code == 200
        data = response.get_json()
        assert 'entryCount' in data['data']
        assert 'publicEntryCount' in data['data']
        assert 'userCount' in data['data']
    
    def test_graphql_invalid_query(self, client):
        """Test GraphQL with invalid query."""
        query = """
        query {
            invalidField
        }
        """
        
        response = client.post('/api/v1/graphql',
                              json={'query': query})
        
        assert response.status_code == 200
        data = response.get_json()
        assert 'errors' in data
    
    def test_graphql_playground_get(self, client):
        """Test GraphQL playground interface."""
        response = client.get('/api/v1/graphql')
        
        assert response.status_code == 200
        assert b'GraphQL Playground' in response.data
# File: app/api_hub/pagination.py
# 🔌 API Pagination Utilities

from flask import request, url_for, current_app
from math import ceil


def paginate_query(query, page=1, per_page=20, max_per_page=100):
    """
    Paginate a SQLAlchemy query and return results with metadata.
    
    Args:
        query: SQLAlchemy query object
        page: Current page number (1-based)
        per_page: Items per page
        max_per_page: Maximum items per page allowed
    
    Returns:
        dict: Contains 'items' and 'pagination' metadata
    """
    # Validate and sanitize parameters
    page = max(1, page)
    per_page = min(max(1, per_page), max_per_page)
    
    # Get total count
    total = query.count()
    
    # Calculate pagination metadata
    pages = ceil(total / per_page) if per_page > 0 else 0
    has_prev = page > 1
    has_next = page < pages
    
    # Get items for current page
    offset = (page - 1) * per_page
    items = query.offset(offset).limit(per_page).all()
    
    # Build pagination metadata
    pagination = {
        'page': page,
        'per_page': per_page,
        'total': total,
        'pages': pages,
        'has_prev': has_prev,
        'has_next': has_next,
        'prev_num': page - 1 if has_prev else None,
        'next_num': page + 1 if has_next else None
    }
    
    # Add URLs if endpoint is available
    try:
        endpoint = request.endpoint
        if endpoint:
            args = request.args.copy()
            
            if has_prev:
                args['page'] = page - 1
                pagination['prev_url'] = url_for(endpoint, **args, _external=True)
            else:
                pagination['prev_url'] = None
            
            if has_next:
                args['page'] = page + 1
                pagination['next_url'] = url_for(endpoint, **args, _external=True)
            else:
                pagination['next_url'] = None
            
            # First and last page URLs
            args['page'] = 1
            pagination['first_url'] = url_for(endpoint, **args, _external=True)
            
            if pages > 1:
                args['page'] = pages
                pagination['last_url'] = url_for(endpoint, **args, _external=True)
            else:
                pagination['last_url'] = pagination['first_url']
    
    except RuntimeError:
        # Outside of request context
        pagination.update({
            'prev_url': None,
            'next_url': None,
            'first_url': None,
            'last_url': None
        })
    
    return {
        'items': items,
        'pagination': pagination
    }


def get_pagination_params(default_per_page=20, max_per_page=100):
    """
    Extract and validate pagination parameters from request.
    
    Args:
        default_per_page: Default items per page
        max_per_page: Maximum items per page allowed
    
    Returns:
        tuple: (page, per_page)
    """
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', default_per_page, type=int)
    
    # Validate parameters
    page = max(1, page)
    per_page = min(max(1, per_page), max_per_page)
    
    return page, per_page


def create_pagination_links(pagination, endpoint, **url_kwargs):
    """
    Create pagination links for API responses.
    
    Args:
        pagination: Pagination metadata dict
        endpoint: Flask endpoint name
        **url_kwargs: Additional URL parameters
    
    Returns:
        dict: Pagination links
    """
    links = {}
    args = request.args.copy()
    args.update(url_kwargs)
    
    # Self link
    args['page'] = pagination['page']
    links['self'] = url_for(endpoint, **args, _external=True)
    
    # First page link
    args['page'] = 1
    links['first'] = url_for(endpoint, **args, _external=True)
    
    # Last page link
    if pagination['pages'] > 0:
        args['page'] = pagination['pages']
        links['last'] = url_for(endpoint, **args, _external=True)
    
    # Previous page link
    if pagination['has_prev']:
        args['page'] = pagination['prev_num']
        links['prev'] = url_for(endpoint, **args, _external=True)
    
    # Next page link
    if pagination['has_next']:
        args['page'] = pagination['next_num']
        links['next'] = url_for(endpoint, **args, _external=True)
    
    return links


def paginate_cursor_based(query, cursor=None, per_page=20, cursor_field='id'):
    """
    Implement cursor-based pagination for large datasets.
    
    Args:
        query: SQLAlchemy query object
        cursor: Current cursor value
        per_page: Items per page
        cursor_field: Field to use for cursor (default: 'id')
    
    Returns:
        dict: Contains 'items', 'next_cursor', and 'has_more'
    """
    # Apply cursor filter if provided
    if cursor:
        cursor_attr = getattr(query.column_descriptions[0]['type'], cursor_field)
        query = query.filter(cursor_attr > cursor)
    
    # Get one extra item to check if there are more results
    items = query.limit(per_page + 1).all()
    
    # Check if there are more items
    has_more = len(items) > per_page
    if has_more:
        items = items[:-1]  # Remove the extra item
    
    # Get next cursor
    next_cursor = None
    if has_more and items:
        next_cursor = getattr(items[-1], cursor_field)
    
    return {
        'items': items,
        'next_cursor': next_cursor,
        'has_more': has_more,
        'per_page': per_page
    }


class APIPagination:
    """
    Enhanced pagination class for API responses.
    """
    
    def __init__(self, query, page=1, per_page=20, max_per_page=100):
        """
        Initialize pagination.
        
        Args:
            query: SQLAlchemy query object
            page: Current page number
            per_page: Items per page
            max_per_page: Maximum items per page allowed
        """
        self.query = query
        self.page = max(1, page)
        self.per_page = min(max(1, per_page), max_per_page)
        self.max_per_page = max_per_page
        
        # Calculate totals
        self.total = query.count()
        self.pages = ceil(self.total / self.per_page) if self.per_page > 0 else 0
        
        # Calculate navigation
        self.has_prev = self.page > 1
        self.has_next = self.page < self.pages
        self.prev_num = self.page - 1 if self.has_prev else None
        self.next_num = self.page + 1 if self.has_next else None
        
        # Get items
        offset = (self.page - 1) * self.per_page
        self.items = query.offset(offset).limit(self.per_page).all()
    
    def to_dict(self):
        """Convert pagination to dictionary."""
        return {
            'page': self.page,
            'per_page': self.per_page,
            'total': self.total,
            'pages': self.pages,
            'has_prev': self.has_prev,
            'has_next': self.has_next,
            'prev_num': self.prev_num,
            'next_num': self.next_num
        }
    
    def get_links(self, endpoint, **url_kwargs):
        """Get pagination links."""
        return create_pagination_links(self.to_dict(), endpoint, **url_kwargs)
    
    def iter_pages(self, left_edge=2, left_current=2, right_current=3, right_edge=2):
        """
        Iterate over page numbers for pagination display.
        
        Args:
            left_edge: Pages to show at the beginning
            left_current: Pages to show left of current page
            right_current: Pages to show right of current page
            right_edge: Pages to show at the end
        
        Yields:
            int or None: Page numbers or None for gaps
        """
        last = self.pages
        
        for num in range(1, min(left_edge + 1, last + 1)):
            yield num
        
        if left_edge + 1 < self.page - left_current:
            yield None
        
        for num in range(max(left_edge + 1, self.page - left_current), 
                        min(last + 1, self.page + right_current + 1)):
            yield num
        
        if self.page + right_current < last - right_edge:
            yield None
        
        for num in range(max(self.page + right_current + 1, last - right_edge + 1), 
                        last + 1):
            yield num


def paginate_search_results(search_results, page=1, per_page=20, total_results=None):
    """
    Paginate search results that might come from external sources.
    
    Args:
        search_results: List of search results
        page: Current page number
        per_page: Items per page
        total_results: Total number of results (if known)
    
    Returns:
        dict: Paginated results with metadata
    """
    page = max(1, page)
    start_index = (page - 1) * per_page
    end_index = start_index + per_page
    
    # Get items for current page
    items = search_results[start_index:end_index]
    
    # Calculate pagination metadata
    if total_results is None:
        total_results = len(search_results)
    
    pages = ceil(total_results / per_page) if per_page > 0 else 0
    has_prev = page > 1
    has_next = start_index + len(items) < total_results
    
    return {
        'items': items,
        'pagination': {
            'page': page,
            'per_page': per_page,
            'total': total_results,
            'pages': pages,
            'has_prev': has_prev,
            'has_next': has_next,
            'prev_num': page - 1 if has_prev else None,
            'next_num': page + 1 if has_next else None
        }
    }


# Utility function to validate pagination parameters
def validate_pagination_params(page, per_page, max_per_page=100):
    """
    Validate and sanitize pagination parameters.
    
    Args:
        page: Page number
        per_page: Items per page
        max_per_page: Maximum items per page allowed
    
    Returns:
        tuple: Validated (page, per_page)
    
    Raises:
        ValueError: If parameters are invalid
    """
    try:
        page = int(page) if page is not None else 1
        per_page = int(per_page) if per_page is not None else 20
    except (ValueError, TypeError):
        raise ValueError("Page and per_page must be integers")
    
    if page < 1:
        raise ValueError("Page must be greater than 0")
    
    if per_page < 1:
        raise ValueError("Per page must be greater than 0")
    
    if per_page > max_per_page:
        raise ValueError(f"Per page cannot exceed {max_per_page}")
    
    return page, per_page
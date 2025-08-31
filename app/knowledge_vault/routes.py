# File: app/knowledge_vault/routes.py
# 📚 Knowledge Vault CRUD Routes

from flask import render_template, request, redirect, url_for, flash, abort, jsonify, current_app
from flask_login import login_required, current_user
from sqlalchemy import or_, desc, asc
from werkzeug.utils import secure_filename
import os
from datetime import datetime

from . import knowledge_vault
from .forms import KnowledgeEntryForm, SearchForm, BulkDeleteForm
from ..models import KnowledgeEntry, db
from ..utils.cache_utils import cache
from ..auth.decorators import role_required


@knowledge_vault.route('/')
@knowledge_vault.route('/index')
def index():
    """Knowledge vault main page with pagination and search."""
    page = request.args.get('page', 1, type=int)
    per_page = current_app.config.get('POSTS_PER_PAGE', 10)
    
    search_form = SearchForm()
    query = request.args.get('query', '')
    category = request.args.get('category', '')
    sort_by = request.args.get('sort', 'created_desc')
    
    # Build the query
    entries_query = KnowledgeEntry.query
    
    # Apply search filter
    if query:
        entries_query = entries_query.filter(
            or_(
                KnowledgeEntry.title.contains(query),
                KnowledgeEntry.content.contains(query),
                KnowledgeEntry.tags.contains(query)
            )
        )
    
    # Apply category filter
    if category:
        entries_query = entries_query.filter(KnowledgeEntry.category == category)
    
    # Only show public entries for non-authenticated users
    if not current_user.is_authenticated:
        entries_query = entries_query.filter(KnowledgeEntry.is_public == True)
    
    # Apply sorting
    if sort_by == 'created_asc':
        entries_query = entries_query.order_by(asc(KnowledgeEntry.created_at))
    elif sort_by == 'title_asc':
        entries_query = entries_query.order_by(asc(KnowledgeEntry.title))
    elif sort_by == 'title_desc':
        entries_query = entries_query.order_by(desc(KnowledgeEntry.title))
    else:  # default: created_desc
        entries_query = entries_query.order_by(desc(KnowledgeEntry.created_at))
    
    # Paginate results
    entries = entries_query.paginate(
        page=page,
        per_page=per_page,
        error_out=False
    )
    
    # Get featured entries
    featured_entries = KnowledgeEntry.query.filter_by(is_featured=True).limit(5).all()
    
    return render_template(
        'knowledge_vault/vault_index.html',
        entries=entries,
        search_form=search_form,
        query=query,
        category=category,
        sort_by=sort_by,
        featured_entries=featured_entries
    )


@knowledge_vault.route('/entry/<int:id>')
def detail(id):
    """Display a single knowledge entry."""
    entry = KnowledgeEntry.query.get_or_404(id)
    
    # Check if user can view this entry
    if not entry.is_public and (not current_user.is_authenticated or entry.author != current_user):
        abort(403)
    
    # Get related entries by category or tags
    related_entries = KnowledgeEntry.query.filter(
        KnowledgeEntry.id != entry.id,
        or_(
            KnowledgeEntry.category == entry.category,
            KnowledgeEntry.tags.contains(entry.tags.split(',')[0] if entry.tags else '')
        )
    ).filter_by(is_public=True).limit(5).all()
    
    return render_template(
        'knowledge_vault/vault_detail.html',
        entry=entry,
        related_entries=related_entries
    )


@knowledge_vault.route('/create', methods=['GET', 'POST'])
@login_required
def create():
    """Create a new knowledge entry."""
    form = KnowledgeEntryForm()
    
    if form.validate_on_submit():
        # Handle file upload
        filename = None
        if form.attachment.data:
            filename = secure_filename(form.attachment.data.filename)
            upload_path = os.path.join(current_app.config['UPLOAD_FOLDER'], 'vault', filename)
            os.makedirs(os.path.dirname(upload_path), exist_ok=True)
            form.attachment.data.save(upload_path)
        
        # Create new entry
        entry = KnowledgeEntry(
            title=form.title.data,
            description=form.description.data,
            content=form.content.data,
            category=form.category.data,
            tags=form.tags.data,
            source_url=form.source_url.data,
            attachment_filename=filename,
            is_public=form.is_public.data,
            is_featured=form.is_featured.data,
            author_id=current_user.id
        )
        
        try:
            db.session.add(entry)
            db.session.commit()
            flash('Knowledge entry created successfully!', 'success')
            return redirect(url_for('knowledge_vault.detail', id=entry.id))
        except Exception as e:
            db.session.rollback()
            flash('Error creating knowledge entry. Please try again.', 'error')
            current_app.logger.error(f'Error creating knowledge entry: {e}')
    
    return render_template('knowledge_vault/vault_create.html', form=form)


@knowledge_vault.route('/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def edit(id):
    """Edit a knowledge entry."""
    entry = KnowledgeEntry.query.get_or_404(id)
    
    # Check if user can edit this entry
    if entry.author != current_user and not current_user.is_admin:
        abort(403)
    
    form = KnowledgeEntryForm(obj=entry)
    
    if form.validate_on_submit():
        # Handle file upload
        if form.attachment.data:
            filename = secure_filename(form.attachment.data.filename)
            upload_path = os.path.join(current_app.config['UPLOAD_FOLDER'], 'vault', filename)
            os.makedirs(os.path.dirname(upload_path), exist_ok=True)
            form.attachment.data.save(upload_path)
            entry.attachment_filename = filename
        
        # Update entry
        form.populate_obj(entry)
        entry.updated_at = datetime.utcnow()
        
        try:
            db.session.commit()
            flash('Knowledge entry updated successfully!', 'success')
            return redirect(url_for('knowledge_vault.detail', id=entry.id))
        except Exception as e:
            db.session.rollback()
            flash('Error updating knowledge entry. Please try again.', 'error')
            current_app.logger.error(f'Error updating knowledge entry: {e}')
    
    return render_template('knowledge_vault/vault_edit.html', form=form, entry=entry)


@knowledge_vault.route('/delete/<int:id>', methods=['POST'])
@login_required
def delete(id):
    """Delete a knowledge entry."""
    entry = KnowledgeEntry.query.get_or_404(id)
    
    # Check if user can delete this entry
    if entry.author != current_user and not current_user.is_admin:
        abort(403)
    
    try:
        # Delete associated file if exists
        if entry.attachment_filename:
            file_path = os.path.join(current_app.config['UPLOAD_FOLDER'], 'vault', entry.attachment_filename)
            if os.path.exists(file_path):
                os.remove(file_path)
        
        db.session.delete(entry)
        db.session.commit()
        flash('Knowledge entry deleted successfully!', 'success')
    except Exception as e:
        db.session.rollback()
        flash('Error deleting knowledge entry. Please try again.', 'error')
        current_app.logger.error(f'Error deleting knowledge entry: {e}')
    
    return redirect(url_for('knowledge_vault.index'))


@knowledge_vault.route('/bulk-actions', methods=['POST'])
@login_required
@role_required('admin')
def bulk_actions():
    """Handle bulk actions on knowledge entries."""
    form = BulkDeleteForm()
    
    if form.validate_on_submit():
        entry_ids = [int(id.strip()) for id in form.entry_ids.data.split(',') if id.strip().isdigit()]
        action = form.action.data
        
        entries = KnowledgeEntry.query.filter(KnowledgeEntry.id.in_(entry_ids)).all()
        
        try:
            if action == 'delete':
                for entry in entries:
                    if entry.attachment_filename:
                        file_path = os.path.join(current_app.config['UPLOAD_FOLDER'], 'vault', entry.attachment_filename)
                        if os.path.exists(file_path):
                            os.remove(file_path)
                    db.session.delete(entry)
            elif action == 'make_public':
                for entry in entries:
                    entry.is_public = True
            elif action == 'make_private':
                for entry in entries:
                    entry.is_public = False
            
            db.session.commit()
            flash(f'Bulk action "{action}" completed successfully on {len(entries)} entries!', 'success')
        except Exception as e:
            db.session.rollback()
            flash('Error performing bulk action. Please try again.', 'error')
            current_app.logger.error(f'Error in bulk action: {e}')
    
    return redirect(url_for('knowledge_vault.index'))


@knowledge_vault.route('/api/entries')
@cache.cached(timeout=300)
def api_entries():
    """API endpoint for knowledge entries (JSON)."""
    page = request.args.get('page', 1, type=int)
    per_page = min(request.args.get('per_page', 10, type=int), 100)
    
    entries = KnowledgeEntry.query.filter_by(is_public=True).paginate(
        page=page, per_page=per_page, error_out=False
    )
    
    return jsonify({
        'entries': [{
            'id': entry.id,
            'title': entry.title,
            'description': entry.description,
            'category': entry.category,
            'tags': entry.tags.split(',') if entry.tags else [],
            'created_at': entry.created_at.isoformat(),
            'author': entry.author.username if entry.author else 'Unknown'
        } for entry in entries.items],
        'pagination': {
            'page': entries.page,
            'pages': entries.pages,
            'per_page': entries.per_page,
            'total': entries.total,
            'has_next': entries.has_next,
            'has_prev': entries.has_prev
        }
    })


@knowledge_vault.route('/categories')
def categories():
    """Get available categories with entry counts."""
    categories = db.session.query(
        KnowledgeEntry.category,
        db.func.count(KnowledgeEntry.id).label('count')
    ).filter_by(is_public=True).group_by(KnowledgeEntry.category).all()
    
    return jsonify({
        'categories': [{'name': cat, 'count': count} for cat, count in categories]
    })


@knowledge_vault.route('/search-suggestions')
def search_suggestions():
    """Get search suggestions based on query."""
    query = request.args.get('q', '').lower()
    if not query or len(query) < 2:
        return jsonify({'suggestions': []})
    
    # Get title suggestions
    titles = KnowledgeEntry.query.filter(
        KnowledgeEntry.title.contains(query),
        KnowledgeEntry.is_public == True
    ).limit(5).all()
    
    suggestions = [{'text': entry.title, 'type': 'title'} for entry in titles]
    
    # Get tag suggestions
    all_tags = db.session.query(KnowledgeEntry.tags).filter(
        KnowledgeEntry.tags.isnot(None),
        KnowledgeEntry.is_public == True
    ).all()
    
    tag_suggestions = []
    for tag_string in all_tags:
        if tag_string[0]:
            tags = [tag.strip().lower() for tag in tag_string[0].split(',')]
            tag_suggestions.extend([tag for tag in tags if query in tag and len(tag_suggestions) < 5])
    
    suggestions.extend([{'text': tag, 'type': 'tag'} for tag in set(tag_suggestions)])
    
    return jsonify({'suggestions': suggestions[:10]})
# File: app/cli/db_commands.py
# 🖥️ Database Management Commands

import click
from flask.cli import with_appcontext
from flask import current_app
from ..models import db, User, KnowledgeEntry, Category, Tag
from ..utils.seeds import seed_categories, seed_sample_users, seed_sample_entries


@click.group()
def db():
    """Database management commands."""
    pass


@db.command()
@with_appcontext
def init():
    """Initialize the database."""
    db.create_all()
    click.echo('Database tables created successfully.')


@db.command()
@with_appcontext
def drop():
    """Drop all database tables."""
    if click.confirm('Are you sure you want to drop all tables? This will delete all data.'):
        db.drop_all()
        click.echo('All database tables dropped.')
    else:
        click.echo('Operation cancelled.')


@db.command()
@with_appcontext
def reset():
    """Reset the database (drop and recreate)."""
    if click.confirm('Are you sure you want to reset the database? This will delete all data.'):
        db.drop_all()
        db.create_all()
        click.echo('Database reset successfully.')
    else:
        click.echo('Operation cancelled.')


@db.command()
@with_appcontext
def seed():
    """Seed the database with sample data."""
    try:
        # Seed categories
        categories_created = seed_categories()
        click.echo(f'Created {categories_created} categories.')
        
        # Seed sample users
        users_created = seed_sample_users()
        click.echo(f'Created {users_created} sample users.')
        
        # Seed sample entries
        entries_created = seed_sample_entries()
        click.echo(f'Created {entries_created} sample knowledge entries.')
        
        click.echo('Database seeded successfully!')
        
    except Exception as e:
        click.echo(f'Error seeding database: {e}')
        db.session.rollback()


@db.command()
@with_appcontext
def stats():
    """Display database statistics."""
    try:
        user_count = User.query.count()
        entry_count = KnowledgeEntry.query.count()
        public_entry_count = KnowledgeEntry.query.filter_by(is_public=True).count()
        category_count = Category.query.count()
        tag_count = Tag.query.count()
        
        click.echo('\n=== Database Statistics ===')
        click.echo(f'Users: {user_count}')
        click.echo(f'Knowledge Entries: {entry_count}')
        click.echo(f'Public Entries: {public_entry_count}')
        click.echo(f'Categories: {category_count}')
        click.echo(f'Tags: {tag_count}')
        
        # Category breakdown
        from sqlalchemy import func
        categories = db.session.query(
            KnowledgeEntry.category,
            func.count(KnowledgeEntry.id).label('count')
        ).group_by(KnowledgeEntry.category).all()
        
        if categories:
            click.echo('\n=== Entries by Category ===')
            for category, count in categories:
                click.echo(f'{category.title()}: {count}')
        
    except Exception as e:
        click.echo(f'Error getting database stats: {e}')


@db.command()
@with_appcontext
def cleanup():
    """Clean up orphaned records."""
    try:
        # Clean up orphaned entries (no author)
        orphaned_entries = KnowledgeEntry.query.filter(
            ~KnowledgeEntry.author_id.in_(
                db.session.query(User.id)
            )
        ).all()
        
        if orphaned_entries:
            for entry in orphaned_entries:
                db.session.delete(entry)
            db.session.commit()
            click.echo(f'Removed {len(orphaned_entries)} orphaned entries.')
        else:
            click.echo('No orphaned entries found.')
        
        # Update tag usage counts
        tags = Tag.query.all()
        for tag in tags:
            count = KnowledgeEntry.query.filter(
                KnowledgeEntry.tags.contains(tag.name)
            ).count()
            tag.usage_count = count
        
        db.session.commit()
        click.echo('Updated tag usage counts.')
        
        click.echo('Database cleanup completed.')
        
    except Exception as e:
        click.echo(f'Error during cleanup: {e}')
        db.session.rollback()


@db.command()
@click.argument('filename')
@with_appcontext
def backup(filename):
    """Backup database to file."""
    try:
        import json
        from datetime import datetime
        
        backup_data = {
            'timestamp': datetime.utcnow().isoformat(),
            'users': [],
            'entries': [],
            'categories': [],
            'tags': []
        }
        
        # Backup users (without passwords)
        users = User.query.all()
        for user in users:
            backup_data['users'].append({
                'id': user.id,
                'username': user.username,
                'email': user.email,
                'first_name': user.first_name,
                'last_name': user.last_name,
                'is_admin': user.is_admin,
                'is_active': user.is_active,
                'created_at': user.created_at.isoformat()
            })
        
        # Backup entries
        entries = KnowledgeEntry.query.all()
        for entry in entries:
            backup_data['entries'].append({
                'id': entry.id,
                'title': entry.title,
                'description': entry.description,
                'content': entry.content,
                'category': entry.category,
                'tags': entry.tags,
                'is_public': entry.is_public,
                'is_featured': entry.is_featured,
                'author_id': entry.author_id,
                'created_at': entry.created_at.isoformat()
            })
        
        # Backup categories
        categories = Category.query.all()
        for category in categories:
            backup_data['categories'].append({
                'name': category.name,
                'display_name': category.display_name,
                'description': category.description,
                'color': category.color
            })
        
        with open(filename, 'w') as f:
            json.dump(backup_data, f, indent=2)
        
        click.echo(f'Database backup saved to {filename}')
        
    except Exception as e:
        click.echo(f'Error creating backup: {e}')


@db.command()
@click.argument('filename')
@with_appcontext
def restore(filename):
    """Restore database from backup file."""
    if not click.confirm('Are you sure? This will overwrite existing data.'):
        click.echo('Operation cancelled.')
        return
    
    try:
        import json
        
        with open(filename, 'r') as f:
            backup_data = json.load(f)
        
        # Clear existing data
        db.drop_all()
        db.create_all()
        
        # Restore categories first
        for cat_data in backup_data.get('categories', []):
            category = Category(**cat_data)
            db.session.add(category)
        
        # Restore users
        for user_data in backup_data.get('users', []):
            user_data.pop('id', None)  # Let DB assign new IDs
            user = User(**user_data)
            user.set_password('defaultpassword123')  # Set default password
            db.session.add(user)
        
        db.session.commit()
        click.echo('Database restored successfully.')
        click.echo('Note: User passwords have been reset to "defaultpassword123"')
        
    except FileNotFoundError:
        click.echo(f'Backup file {filename} not found.')
    except Exception as e:
        click.echo(f'Error restoring backup: {e}')
        db.session.rollback()
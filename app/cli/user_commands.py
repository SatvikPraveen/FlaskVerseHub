# File: app/cli/user_commands.py
# 🖥️ User Management Commands

import click
from flask.cli import with_appcontext
import getpass
from ..models import db, User, KnowledgeEntry
from ..security.password_utils import validate_password_policy


@click.group()
def user():
    """User management commands."""
    pass


@user.command()
@with_appcontext
def create_admin():
    """Create an admin user."""
    click.echo('Creating admin user...')
    
    username = click.prompt('Username', type=str)
    email = click.prompt('Email', type=str)
    
    # Check if user already exists
    existing_user = User.query.filter(
        (User.username == username.lower()) |
        (User.email == email.lower())
    ).first()
    
    if existing_user:
        click.echo('Error: User with this username or email already exists.')
        return
    
    # Get password securely
    while True:
        password = getpass.getpass('Password: ')
        confirm_password = getpass.getpass('Confirm password: ')
        
        if password != confirm_password:
            click.echo('Passwords do not match. Please try again.')
            continue
        
        # Validate password
        is_valid, errors = validate_password_policy(password, username, email)
        if not is_valid:
            click.echo('Password does not meet requirements:')
            for error in errors:
                click.echo(f'  - {error}')
            continue
        
        break
    
    # Get optional fields
    first_name = click.prompt('First name (optional)', default='', show_default=False)
    last_name = click.prompt('Last name (optional)', default='', show_default=False)
    
    try:
        # Create admin user
        admin = User(
            username=username.lower(),
            email=email.lower(),
            first_name=first_name or None,
            last_name=last_name or None,
            is_admin=True,
            is_active=True,
            email_verified=True
        )
        admin.set_password(password)
        
        db.session.add(admin)
        db.session.commit()
        
        click.echo(f'Admin user "{username}" created successfully!')
        
    except Exception as e:
        db.session.rollback()
        click.echo(f'Error creating admin user: {e}')


@user.command()
@click.argument('username')
@with_appcontext
def make_admin(username):
    """Make a user an admin."""
    user = User.query.filter_by(username=username.lower()).first()
    
    if not user:
        click.echo(f'User "{username}" not found.')
        return
    
    if user.is_admin:
        click.echo(f'User "{username}" is already an admin.')
        return
    
    user.is_admin = True
    db.session.commit()
    
    click.echo(f'User "{username}" is now an admin.')


@user.command()
@click.argument('username')
@with_appcontext
def remove_admin(username):
    """Remove admin privileges from a user."""
    user = User.query.filter_by(username=username.lower()).first()
    
    if not user:
        click.echo(f'User "{username}" not found.')
        return
    
    if not user.is_admin:
        click.echo(f'User "{username}" is not an admin.')
        return
    
    # Check if this is the last admin
    admin_count = User.query.filter_by(is_admin=True).count()
    if admin_count <= 1:
        click.echo('Cannot remove admin privileges from the last admin user.')
        return
    
    user.is_admin = False
    db.session.commit()
    
    click.echo(f'Admin privileges removed from user "{username}".')


@user.command()
@click.argument('username')
@with_appcontext
def activate(username):
    """Activate a user account."""
    user = User.query.filter_by(username=username.lower()).first()
    
    if not user:
        click.echo(f'User "{username}" not found.')
        return
    
    if user.is_active:
        click.echo(f'User "{username}" is already active.')
        return
    
    user.is_active = True
    db.session.commit()
    
    click.echo(f'User "{username}" has been activated.')


@user.command()
@click.argument('username')
@with_appcontext
def deactivate(username):
    """Deactivate a user account."""
    user = User.query.filter_by(username=username.lower()).first()
    
    if not user:
        click.echo(f'User "{username}" not found.')
        return
    
    if not user.is_active:
        click.echo(f'User "{username}" is already deactivated.')
        return
    
    # Prevent deactivating the last admin
    if user.is_admin:
        admin_count = User.query.filter_by(is_admin=True, is_active=True).count()
        if admin_count <= 1:
            click.echo('Cannot deactivate the last active admin user.')
            return
    
    user.is_active = False
    db.session.commit()
    
    click.echo(f'User "{username}" has been deactivated.')


@user.command()
@click.argument('username')
@with_appcontext
def delete(username):
    """Delete a user account and all associated data."""
    user = User.query.filter_by(username=username.lower()).first()
    
    if not user:
        click.echo(f'User "{username}" not found.')
        return
    
    # Prevent deleting the last admin
    if user.is_admin:
        admin_count = User.query.filter_by(is_admin=True).count()
        if admin_count <= 1:
            click.echo('Cannot delete the last admin user.')
            return
    
    # Show what will be deleted
    entry_count = user.knowledge_entries.count()
    click.echo(f'User "{username}" has {entry_count} knowledge entries.')
    
    if not click.confirm(f'Are you sure you want to delete user "{username}" and all associated data?'):
        click.echo('Operation cancelled.')
        return
    
    try:
        db.session.delete(user)
        db.session.commit()
        click.echo(f'User "{username}" and all associated data has been deleted.')
        
    except Exception as e:
        db.session.rollback()
        click.echo(f'Error deleting user: {e}')


@user.command()
@click.argument('username')
@with_appcontext
def reset_password(username):
    """Reset a user's password."""
    user = User.query.filter_by(username=username.lower()).first()
    
    if not user:
        click.echo(f'User "{username}" not found.')
        return
    
    # Get new password
    while True:
        password = getpass.getpass('New password: ')
        confirm_password = getpass.getpass('Confirm password: ')
        
        if password != confirm_password:
            click.echo('Passwords do not match. Please try again.')
            continue
        
        # Validate password
        is_valid, errors = validate_password_policy(password, user.username, user.email)
        if not is_valid:
            click.echo('Password does not meet requirements:')
            for error in errors:
                click.echo(f'  - {error}')
            continue
        
        break
    
    try:
        user.set_password(password)
        db.session.commit()
        click.echo(f'Password reset for user "{username}".')
        
    except Exception as e:
        db.session.rollback()
        click.echo(f'Error resetting password: {e}')


@user.command()
@with_appcontext
def list():
    """List all users."""
    users = User.query.order_by(User.created_at.desc()).all()
    
    if not users:
        click.echo('No users found.')
        return
    
    click.echo(f'\n{"ID":<4} {"Username":<20} {"Email":<30} {"Admin":<6} {"Active":<7} {"Entries":<8} {"Created":<12}')
    click.echo('-' * 95)
    
    for user in users:
        entry_count = user.knowledge_entries.count()
        created = user.created_at.strftime('%Y-%m-%d')
        admin = 'Yes' if user.is_admin else 'No'
        active = 'Yes' if user.is_active else 'No'
        
        click.echo(f'{user.id:<4} {user.username[:19]:<20} {user.email[:29]:<30} {admin:<6} {active:<7} {entry_count:<8} {created:<12}')


@user.command()
@click.argument('username')
@with_appcontext
def info(username):
    """Show detailed information about a user."""
    user = User.query.filter_by(username=username.lower()).first()
    
    if not user:
        click.echo(f'User "{username}" not found.')
        return
    
    entry_count = user.knowledge_entries.count()
    public_entries = user.knowledge_entries.filter_by(is_public=True).count()
    
    click.echo(f'\n=== User Information ===')
    click.echo(f'ID: {user.id}')
    click.echo(f'Username: {user.username}')
    click.echo(f'Email: {user.email}')
    click.echo(f'Full Name: {user.full_name}')
    click.echo(f'Admin: {"Yes" if user.is_admin else "No"}')
    click.echo(f'Active: {"Yes" if user.is_active else "No"}')
    click.echo(f'Email Verified: {"Yes" if user.email_verified else "No"}')
    click.echo(f'Created: {user.created_at.strftime("%Y-%m-%d %H:%M")}')
    click.echo(f'Last Login: {user.last_login.strftime("%Y-%m-%d %H:%M") if user.last_login else "Never"}')
    click.echo(f'Knowledge Entries: {entry_count} ({public_entries} public)')
    
    if user.bio:
        click.echo(f'Bio: {user.bio}')


@user.command()
@with_appcontext
def stats():
    """Show user statistics."""
    total_users = User.query.count()
    active_users = User.query.filter_by(is_active=True).count()
    admin_users = User.query.filter_by(is_admin=True).count()
    verified_users = User.query.filter_by(email_verified=True).count()
    
    # Users with entries
    users_with_entries = db.session.query(User.id).join(KnowledgeEntry).distinct().count()
    
    click.echo('\n=== User Statistics ===')
    click.echo(f'Total Users: {total_users}')
    click.echo(f'Active Users: {active_users}')
    click.echo(f'Admin Users: {admin_users}')
    click.echo(f'Verified Users: {verified_users}')
    click.echo(f'Users with Entries: {users_with_entries}')
    
    # Recent registrations
    from datetime import datetime, timedelta
    week_ago = datetime.utcnow() - timedelta(days=7)
    recent_users = User.query.filter(User.created_at >= week_ago).count()
    click.echo(f'New Users (Last 7 days): {recent_users}')
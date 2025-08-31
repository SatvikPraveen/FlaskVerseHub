# File: FlaskVerseHub/manage.py
#!/usr/bin/env python3

import os
from flask.cli import FlaskGroup
from app import create_app, db
from app.models import User, KnowledgeItem
from app.cli import db_commands, user_commands

def create_cli_app():
    """Create Flask app for CLI operations."""
    config_name = os.getenv('FLASK_CONFIG', 'development')
    return create_app(config_name)

cli = FlaskGroup(create_app=create_cli_app)

# Register custom CLI commands
cli.add_command(db_commands.db_cli)
cli.add_command(user_commands.user_cli)

@cli.command()
def init_db():
    """Initialize the database with tables and seed data."""
    db.create_all()
    print("Database tables created successfully!")
    
    # Create default admin user
    if not User.query.filter_by(email='admin@flaskversehub.com').first():
        admin = User(
            username='admin',
            email='admin@flaskversehub.com',
            first_name='Admin',
            last_name='User',
            is_admin=True,
            is_active=True
        )
        admin.set_password('admin123')
        db.session.add(admin)
        db.session.commit()
        print("Admin user created: admin@flaskversehub.com / admin123")

@cli.command()
def seed_data():
    """Seed the database with sample data."""
    from app.utils.seeds import seed_knowledge_items
    seed_knowledge_items()
    print("Sample data seeded successfully!")

@cli.command()
def routes():
    """Display all registered routes."""
    from flask import current_app
    output = []
    for rule in current_app.url_map.iter_rules():
        methods = ','.join(rule.methods)
        line = f"{rule.endpoint:30s} {methods:20s} {rule}"
        output.append(line)
    
    for line in sorted(output):
        print(line)

if __name__ == '__main__':
    cli()
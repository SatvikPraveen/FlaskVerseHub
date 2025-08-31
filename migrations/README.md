# File: migrations/README

Flask-Migrate Database Migration Instructions

This directory contains database migration files for the FlaskVerseHub application.

## Common Commands:

Initialize migrations (first time only):
flask db init

Create a new migration:
flask db migrate -m "Description of changes"

Apply migrations:
flask db upgrade

Rollback to previous migration:
flask db downgrade

Show current migration:
flask db current

Show migration history:
flask db history

## Migration Files:

Migration files are stored in the versions/ directory and are automatically generated.
Each migration file contains:

- upgrade() function: Apply the migration
- downgrade() function: Rollback the migration

## Best Practices:

1. Always review generated migrations before applying
2. Test migrations on development data first
3. Backup production database before applying migrations
4. Never edit migration files manually after they're applied
5. Use descriptive messages for migrations

## Troubleshooting:

If migrations get out of sync:

1. Check current database state: flask db current
2. Compare with migration files in versions/
3. If needed, stamp the database: flask db stamp head
4. Or reset migrations: rm -rf migrations/ && flask db init

## Production Deployment:

Always run migrations as part of deployment:
flask db upgrade

For zero-downtime deployments, ensure migrations are backward compatible.

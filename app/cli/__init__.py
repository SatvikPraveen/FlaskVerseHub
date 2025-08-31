# File: app/cli/__init__.py
# 🖥️ CLI Group Registration

import click
from flask.cli import with_appcontext


@click.group()
def cli():
    """FlaskVerseHub CLI commands."""
    pass


# Import command groups
from . import db_commands, user_commands

# Register command groups
cli.add_command(db_commands.db)
cli.add_command(user_commands.user)
"""User administration commands."""

from __future__ import annotations

import click
from flask.cli import AppGroup
from sqlalchemy import select

from app.extensions import db
from app.models import User

users_cli = AppGroup("users", help="Manage user accounts.")


@users_cli.command("create")
@click.argument("username")
@click.argument("email")
@click.option("--password", prompt=True, hide_input=True, confirmation_prompt=True)
@click.option("--admin", is_flag=True, help="Grant administrator privileges.")
def create_user(username: str, email: str, password: str, admin: bool) -> None:
    """Create a user account."""
    if db.session.scalar(select(User).where((User.username == username) | (User.email == email))):
        raise click.ClickException("a user with that username or email already exists")
    user = User(username=username, email=email, is_admin=admin, email_verified=True)
    user.set_password(password)
    db.session.add(user)
    db.session.commit()
    click.echo(f"Created {'admin ' if admin else ''}user {username} (id={user.id}).")


@users_cli.command("list")
def list_users() -> None:
    """List all users."""
    users = db.session.scalars(select(User).order_by(User.id)).all()
    for user in users:
        flags = " ".join(
            f for f, on in (("admin", user.is_admin), ("locked", user.is_locked)) if on
        )
        click.echo(f"{user.id:>4}  {user.username:<20} {user.email:<30} {flags}")
    click.echo(f"{len(users)} user(s).")


@users_cli.command("promote")
@click.argument("username")
def promote_user(username: str) -> None:
    """Grant administrator privileges."""
    user = db.session.scalar(select(User).where(User.username == username))
    if user is None:
        raise click.ClickException(f"no such user: {username}")
    user.is_admin = True
    db.session.commit()
    click.echo(f"{username} is now an administrator.")


@users_cli.command("unlock")
@click.argument("username")
def unlock_user(username: str) -> None:
    """Clear a login lockout."""
    user = db.session.scalar(select(User).where(User.username == username))
    if user is None:
        raise click.ClickException(f"no such user: {username}")
    user.failed_login_attempts = 0
    user.locked_until = None
    db.session.commit()
    click.echo(f"{username} unlocked.")

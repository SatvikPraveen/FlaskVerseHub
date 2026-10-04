"""Custom ``flask`` sub-commands: ``seed``, ``users`` and ``search``."""

from flask import Flask

from app.cli.seed import seed_cli
from app.cli.users import users_cli


def register_cli(app: Flask) -> None:
    app.cli.add_command(seed_cli)
    app.cli.add_command(users_cli)


__all__ = ["register_cli"]

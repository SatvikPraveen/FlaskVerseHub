"""WSGI entry point. ``gunicorn -k gevent -w 1 wsgi:app`` or ``flask --app wsgi run``."""

from app import create_app
from app.extensions import socketio

app = create_app()

if __name__ == "__main__":  # pragma: no cover
    socketio.run(app, host="0.0.0.0", port=5000, debug=app.debug)  # noqa: S104

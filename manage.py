#!/usr/bin/env python
"""Development server with WebSocket support.

Equivalent to ``flask --app wsgi run`` but served through Flask-SocketIO so
real-time features work without gunicorn/gevent.
"""

from __future__ import annotations

import os

from app import create_app
from app.extensions import socketio


def main() -> None:
    app = create_app(os.environ.get("FLASK_CONFIG", "development"))
    host = os.environ.get("HOST", "127.0.0.1")
    port = int(os.environ.get("PORT", "5000"))
    socketio.run(app, host=host, port=port, debug=app.debug, use_reloader=app.debug)


if __name__ == "__main__":
    main()

"""Socket.IO channels.

Rooms
-----
* ``public``        - every connected client; receives item lifecycle events
* ``user:<id>``     - one per authenticated user; receives notifications
* ``item:<slug>``   - clients viewing an item; receives comment/update events

The HTTP session cookie authenticates the socket: the handshake reads
Flask-Login's user id from the session, so no separate token exchange is
needed and no database query runs per connection.
"""

from __future__ import annotations

import threading
from typing import Any

from flask import request, session
from flask_socketio import emit, join_room, leave_room

from app.extensions import socketio
from app.utils.time import utcnow

_presence_lock = threading.Lock()
_connected: dict[str, int | None] = {}


def connected_count() -> int:
    with _presence_lock:
        return len(_connected)


def _broadcast_presence() -> None:
    socketio.emit(
        "presence", {"connected": connected_count(), "at": utcnow().isoformat()}, to="public"
    )


@socketio.on("connect")
def _on_connect(_auth: Any = None) -> None:
    sid = request.sid  # type: ignore[attr-defined]
    raw_user_id = session.get("_user_id")  # Flask-Login's session key; avoids a DB round-trip
    user_id = int(raw_user_id) if isinstance(raw_user_id, str) and raw_user_id.isdigit() else None
    with _presence_lock:
        _connected[sid] = user_id
    join_room("public")
    if user_id is not None:
        join_room(f"user:{user_id}")
    emit(
        "connected",
        {"sid": sid, "authenticated": user_id is not None, "connected": connected_count()},
    )
    _broadcast_presence()


@socketio.on("disconnect")
def _on_disconnect(*_args: Any) -> None:
    sid = request.sid  # type: ignore[attr-defined]
    with _presence_lock:
        _connected.pop(sid, None)
    _broadcast_presence()


@socketio.on("subscribe")
def _on_subscribe(data: dict[str, Any] | None) -> None:
    slug = (data or {}).get("item")
    if isinstance(slug, str) and slug:
        join_room(f"item:{slug}")
        emit("subscribed", {"item": slug})


@socketio.on("unsubscribe")
def _on_unsubscribe(data: dict[str, Any] | None) -> None:
    slug = (data or {}).get("item")
    if isinstance(slug, str) and slug:
        leave_room(f"item:{slug}")


@socketio.on("ping_server")
def _on_ping(_data: Any = None) -> None:
    emit("pong_client", {"at": utcnow().isoformat()})


__all__ = ["connected_count"]

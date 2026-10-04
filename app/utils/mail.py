"""Asynchronous transactional email built on Flask-Mail."""

from __future__ import annotations

from collections.abc import Sequence
from threading import Thread
from typing import Any

from flask import Flask, current_app, render_template
from flask_mail import Message

from app.extensions import mail
from app.observability import log


def _deliver(app: Flask, message: Message) -> None:
    with app.app_context():
        try:
            mail.send(message)
        except Exception:  # pragma: no cover - network failure path
            log.exception("mail_delivery_failed", subject=message.subject)


def send_email(
    subject: str,
    recipients: str | Sequence[str],
    template: str,
    *,
    sync: bool = False,
    **context: Any,
) -> Message:
    """Render ``templates/email/<template>.{html,txt}`` and send in a worker thread.

    Returns the message so tests can inspect it when ``MAIL_SUPPRESS_SEND`` is set.
    """
    app = current_app._get_current_object()  # type: ignore[attr-defined]
    to: list[str | tuple[str, str]] = (
        [recipients] if isinstance(recipients, str) else list(recipients)
    )
    message = Message(subject=f"[{app.config['APP_NAME']}] {subject}", recipients=to)
    message.body = render_template(f"email/{template}.txt", **context)
    message.html = render_template(f"email/{template}.html", **context)
    if sync or app.config.get("TESTING"):
        _deliver(app, message)
    else:
        Thread(target=_deliver, args=(app, message), daemon=True).start()
    return message


__all__ = ["send_email"]

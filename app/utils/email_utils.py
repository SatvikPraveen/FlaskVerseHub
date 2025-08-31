# File: app/utils/email_utils.py
# 📧 Email Sending (verification, password reset)

from flask import current_app, render_template
from flask_mail import Message
from ..extensions import mail
from threading import Thread


def send_async_email(app, msg):
    """Send email asynchronously."""
    with app.app_context():
        mail.send(msg)


def send_email(to, subject, template, **kwargs):
    """Send email with template."""
    app = current_app._get_current_object()
    
    msg = Message(
        subject=f'[FlaskVerseHub] {subject}',
        sender=app.config['MAIL_DEFAULT_SENDER'],
        recipients=[to] if isinstance(to, str) else to
    )
    
    # Render HTML template
    msg.html = render_template(f'{template}.html', **kwargs)
    
    # Send asynchronously
    thread = Thread(target=send_async_email, args=[app, msg])
    thread.daemon = True
    thread.start()


def send_password_reset_email(user, token):
    """Send password reset email."""
    send_email(
        to=user.email,
        subject='Password Reset Request',
        template='auth/email/reset_password',
        user=user,
        token=token
    )


def send_verification_email(user, token):
    """Send email verification."""
    send_email(
        to=user.email,
        subject='Email Verification',
        template='auth/email/verify_email',
        user=user,
        token=token
    )
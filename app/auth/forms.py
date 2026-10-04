"""WTForms definitions for authentication and account management."""

from __future__ import annotations

import re

from flask_wtf import FlaskForm
from wtforms import (
    BooleanField,
    PasswordField,
    SelectField,
    SelectMultipleField,
    StringField,
    SubmitField,
    TextAreaField,
    URLField,
)
from wtforms.validators import (
    URL,
    DataRequired,
    Email,
    EqualTo,
    Length,
    Optional,
    Regexp,
    ValidationError,
)

USERNAME_RE = r"^[A-Za-z0-9_][A-Za-z0-9_.-]{2,63}$"
PASSWORD_MIN = 10


def strong_password(_form: FlaskForm, field: PasswordField) -> None:
    """At least ``PASSWORD_MIN`` characters mixing letters and digits."""
    value = field.data or ""
    if len(value) < PASSWORD_MIN:
        raise ValidationError(f"Use at least {PASSWORD_MIN} characters.")
    if not re.search(r"[A-Za-z]", value) or not re.search(r"\d", value):
        raise ValidationError("Mix letters and numbers.")


class LoginForm(FlaskForm):
    identifier = StringField(
        "Username or email",
        validators=[DataRequired(), Length(max=255)],
        render_kw={"autofocus": True},
    )
    password = PasswordField("Password", validators=[DataRequired()])
    remember_me = BooleanField("Keep me signed in")
    submit = SubmitField("Sign in")


class RegistrationForm(FlaskForm):
    username = StringField(
        "Username",
        validators=[
            DataRequired(),
            Regexp(USERNAME_RE, message="3-64 characters: letters, digits, '_', '.', '-'."),
        ],
        description="Public handle shown on your contributions.",
    )
    email = StringField("Email", validators=[DataRequired(), Email(), Length(max=255)])
    first_name = StringField("First name", validators=[Optional(), Length(max=64)])
    last_name = StringField("Last name", validators=[Optional(), Length(max=64)])
    password = PasswordField("Password", validators=[DataRequired(), strong_password])
    password_confirm = PasswordField(
        "Confirm password", validators=[DataRequired(), EqualTo("password", "Passwords differ.")]
    )
    accept_terms = BooleanField(
        "I agree to the terms of use", validators=[DataRequired("You must accept the terms.")]
    )
    submit = SubmitField("Create account")


class ProfileForm(FlaskForm):
    first_name = StringField("First name", validators=[Optional(), Length(max=64)])
    last_name = StringField("Last name", validators=[Optional(), Length(max=64)])
    bio = TextAreaField("Bio", validators=[Optional(), Length(max=1000)], render_kw={"rows": 4})
    website = URLField("Website", validators=[Optional(), URL(), Length(max=255)])
    location = StringField("Location", validators=[Optional(), Length(max=128)])
    theme = SelectField("Theme", choices=[("light", "Light"), ("dark", "Dark")])
    email_notifications = BooleanField("Email me about activity on my items")
    submit = SubmitField("Save profile")


class ChangePasswordForm(FlaskForm):
    current_password = PasswordField("Current password", validators=[DataRequired()])
    new_password = PasswordField("New password", validators=[DataRequired(), strong_password])
    confirm = PasswordField(
        "Confirm new password",
        validators=[DataRequired(), EqualTo("new_password", "Passwords differ.")],
    )
    submit = SubmitField("Change password")


class PasswordResetRequestForm(FlaskForm):
    identifier = StringField("Username or email", validators=[DataRequired(), Length(max=255)])
    submit = SubmitField("Send reset link")


class PasswordResetForm(FlaskForm):
    password = PasswordField("New password", validators=[DataRequired(), strong_password])
    confirm = PasswordField(
        "Confirm password", validators=[DataRequired(), EqualTo("password", "Passwords differ.")]
    )
    submit = SubmitField("Reset password")


class ApiKeyForm(FlaskForm):
    name = StringField("Key name", validators=[DataRequired(), Length(max=100)])
    scopes = SelectMultipleField(
        "Scopes",
        choices=[("read", "Read"), ("write", "Write"), ("admin", "Admin")],
        default=["read"],
    )
    submit = SubmitField("Generate key")


class DeleteAccountForm(FlaskForm):
    password = PasswordField("Confirm your password", validators=[DataRequired()])
    submit = SubmitField("Delete my account permanently")


__all__ = [
    "ApiKeyForm",
    "ChangePasswordForm",
    "DeleteAccountForm",
    "LoginForm",
    "PasswordResetForm",
    "PasswordResetRequestForm",
    "ProfileForm",
    "RegistrationForm",
]

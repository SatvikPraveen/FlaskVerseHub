from __future__ import annotations

from flask_wtf import FlaskForm
from wtforms import (
    BooleanField,
    HiddenField,
    SelectField,
    SelectMultipleField,
    StringField,
    SubmitField,
    TextAreaField,
    URLField,
)
from wtforms.validators import URL, DataRequired, Length, Optional

from app.models import Difficulty, ItemStatus


class KnowledgeItemForm(FlaskForm):
    title = StringField("Title", validators=[DataRequired(), Length(min=3, max=200)])
    summary = StringField(
        "Summary",
        validators=[Optional(), Length(max=500)],
        description="One or two sentences shown in listings and search results.",
    )
    content = TextAreaField(
        "Content",
        validators=[DataRequired(), Length(min=10)],
        render_kw={"rows": 16},
        description="Basic HTML is allowed and sanitised on save.",
    )
    category_id = SelectField("Category", coerce=int, validators=[Optional()])
    tags = StringField(
        "Tags",
        validators=[Optional(), Length(max=300)],
        description="Comma-separated, e.g. flask, sqlalchemy",
    )
    difficulty = SelectField(
        "Difficulty",
        choices=[(d.value, d.value.title()) for d in Difficulty],
        default=Difficulty.INTERMEDIATE.value,
    )
    status = SelectField(
        "Status",
        choices=[(s.value, s.value.title()) for s in ItemStatus],
        default=ItemStatus.PUBLISHED.value,
    )
    source_url = URLField("Source URL", validators=[Optional(), URL(), Length(max=512)])
    is_public = BooleanField("Public (visible to everyone)", default=True)
    is_featured = BooleanField("Featured on the home page")
    change_note = StringField(
        "Change note",
        validators=[Optional(), Length(max=255)],
        description="Why did you edit this? (kept in history)",
    )
    submit = SubmitField("Save")


class CommentForm(FlaskForm):
    body = TextAreaField(
        "Comment", validators=[DataRequired(), Length(min=1, max=5000)], render_kw={"rows": 3}
    )
    parent_id = HiddenField()
    submit = SubmitField("Post comment")


class BulkActionForm(FlaskForm):
    action = SelectField(
        "Action",
        choices=[
            ("publish", "Publish"),
            ("archive", "Archive"),
            ("make_public", "Make public"),
            ("make_private", "Make private"),
            ("feature", "Feature"),
            ("unfeature", "Unfeature"),
            ("delete", "Delete"),
        ],
        validators=[DataRequired()],
    )
    item_ids = SelectMultipleField("Items", coerce=int, validate_choice=False)
    submit = SubmitField("Apply")


__all__ = ["BulkActionForm", "CommentForm", "KnowledgeItemForm"]

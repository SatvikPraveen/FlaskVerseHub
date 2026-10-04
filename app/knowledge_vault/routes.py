from __future__ import annotations

from typing import Any

from flask import abort, flash, jsonify, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy import func, select
from werkzeug.wrappers import Response

from app.extensions import db
from app.knowledge_vault import bp, service
from app.knowledge_vault.forms import BulkActionForm, CommentForm, KnowledgeItemForm
from app.models import Bookmark, Category, Comment, KnowledgeItem, KnowledgeItemRevision, Tag
from app.utils.diff import inline_diff
from app.utils.pagination import page_args, paginate


def _viewer() -> Any:
    return current_user if current_user.is_authenticated else None


def _populate_categories(form: KnowledgeItemForm) -> None:
    categories = db.session.scalars(select(Category).order_by(Category.name)).all()
    form.category_id.choices = [(0, "— none —"), *[(c.id, c.name) for c in categories]]


def _item_or_404(slug: str) -> KnowledgeItem:
    item = service.get_by_slug(slug, user=_viewer())
    if item is None:
        abort(404, description="That knowledge item does not exist or you may not view it.")
    return item


def _editable_or_403(slug: str) -> KnowledgeItem:
    item = _item_or_404(slug)
    if not service.can_edit(item, current_user):
        abort(403, description="You may only edit your own items.")
    return item


@bp.get("/")
def index() -> str:
    filters = service.ItemFilters.from_args(request.args, user=_viewer())
    page, per_page = page_args()
    listing = paginate(service.build_listing(filters, user=_viewer()), page, per_page)
    categories = db.session.scalars(select(Category).order_by(Category.name)).all()
    popular_tags = db.session.execute(
        select(Tag, func.count(KnowledgeItem.id).label("n"))
        .join(Tag.items)
        .group_by(Tag.id)
        .order_by(func.count(KnowledgeItem.id).desc(), Tag.name)
        .limit(20)
    ).all()
    bulk_form = BulkActionForm() if current_user.is_authenticated else None
    return render_template(
        "vault/index.html",
        page=listing,
        filters=filters,
        categories=categories,
        popular_tags=popular_tags,
        sort_options=list(service.SORT_OPTIONS),
        bulk_form=bulk_form,
    )


@bp.route("/new", methods=["GET", "POST"])
@login_required
def create() -> Response | str:
    form = KnowledgeItemForm()
    _populate_categories(form)
    if form.validate_on_submit():
        item = service.create_item(form.data, author=current_user)
        flash("Knowledge item created.", "success")
        return redirect(url_for("knowledge_vault.detail", slug=item.slug))
    return render_template("vault/form.html", form=form, item=None)


@bp.get("/<slug>")
def detail(slug: str) -> str:
    item = _item_or_404(slug)
    service.record_view(item)
    comments = item.comments.filter(Comment.parent_id.is_(None)).all()
    related = db.session.scalars(
        KnowledgeItem.visible_to(_viewer())
        .where(KnowledgeItem.id != item.id)
        .where(
            (KnowledgeItem.category_id == item.category_id)
            | KnowledgeItem.tags.any(Tag.id.in_([t.id for t in item.tags] or [0]))
        )
        .order_by(KnowledgeItem.view_count.desc())
        .limit(4)
    ).all()
    return render_template(
        "vault/detail.html",
        item=item,
        comments=comments,
        related=related,
        comment_form=CommentForm(),
        can_edit=service.can_edit(item, _viewer()),
        bookmarked=service.is_bookmarked(item, _viewer()),
        bookmark_count=item.bookmarks.count(),
    )


@bp.route("/<slug>/edit", methods=["GET", "POST"])
@login_required
def edit(slug: str) -> Response | str:
    item = _editable_or_403(slug)
    form = KnowledgeItemForm(obj=item)
    _populate_categories(form)
    if request.method == "GET":
        form.tags.data = ", ".join(item.tag_names)
        form.category_id.data = item.category_id or 0
        form.difficulty.data = item.difficulty.value
        form.status.data = item.status.value
    if form.validate_on_submit():
        service.update_item(item, form.data, actor=current_user, note=form.change_note.data or None)
        flash("Changes saved.", "success")
        return redirect(url_for("knowledge_vault.detail", slug=item.slug))
    return render_template("vault/form.html", form=form, item=item)


@bp.post("/<slug>/delete")
@login_required
def delete(slug: str) -> Response:
    item = _editable_or_403(slug)
    service.delete_item(item, actor=current_user)
    flash("Knowledge item deleted.", "info")
    return redirect(url_for("knowledge_vault.index"))


@bp.get("/<slug>/history")
def history(slug: str) -> str:
    item = _item_or_404(slug)
    revisions = item.revisions.all()
    return render_template("vault/history.html", item=item, revisions=revisions)


@bp.get("/<slug>/history/<int:version>")
def revision(slug: str, version: int) -> str:
    item = _item_or_404(slug)
    rev = item.revisions.filter(KnowledgeItemRevision.version == version).first()
    if rev is None:
        abort(404)
    newer = item.revisions.filter(KnowledgeItemRevision.version == version + 1).first()
    newer_title, newer_content = (
        (newer.title, newer.content) if newer else (item.title, item.content)
    )
    return render_template(
        "vault/revision.html",
        item=item,
        revision=rev,
        title_diff=inline_diff(rev.title, newer_title),
        content_diff=inline_diff(rev.content, newer_content),
        compared_to=newer.version if newer else item.version,
        can_edit=service.can_edit(item, _viewer()),
    )


@bp.post("/<slug>/history/<int:version>/restore")
@login_required
def restore(slug: str, version: int) -> Response:
    item = _editable_or_403(slug)
    rev = item.revisions.filter(KnowledgeItemRevision.version == version).first()
    if rev is None:
        abort(404)
    service.restore_revision(item, rev, actor=current_user)
    flash(f"Restored version {version}.", "success")
    return redirect(url_for("knowledge_vault.detail", slug=item.slug))


@bp.post("/<slug>/bookmark")
@login_required
def bookmark(slug: str) -> Response:
    item = _item_or_404(slug)
    now_bookmarked = service.toggle_bookmark(item, user=current_user)
    if request.accept_mimetypes.best == "application/json" or request.is_json:
        return jsonify({"bookmarked": now_bookmarked, "count": item.bookmarks.count()})
    flash("Bookmarked." if now_bookmarked else "Bookmark removed.", "info")
    return redirect(url_for("knowledge_vault.detail", slug=item.slug))


@bp.get("/bookmarks")
@login_required
def bookmarks() -> str:
    page, per_page = page_args()
    stmt = (
        select(KnowledgeItem)
        .join(Bookmark, Bookmark.item_id == KnowledgeItem.id)
        .where(Bookmark.user_id == current_user.id)
        .order_by(Bookmark.created_at.desc())
    )
    return render_template("vault/bookmarks.html", page=paginate(stmt, page, per_page))


@bp.post("/<slug>/comments")
@login_required
def add_comment(slug: str) -> Response:
    item = _item_or_404(slug)
    form = CommentForm()
    if form.validate_on_submit():
        parent_id = int(form.parent_id.data) if (form.parent_id.data or "").isdigit() else None
        comment = service.add_comment(
            item, form.body.data or "", author=current_user, parent_id=parent_id
        )
        flash("Comment posted.", "success")
        return redirect(
            url_for("knowledge_vault.detail", slug=item.slug) + f"#comment-{comment.id}"
        )
    flash("Comment cannot be empty.", "danger")
    return redirect(url_for("knowledge_vault.detail", slug=item.slug) + "#comments")


@bp.post("/comments/<int:comment_id>/delete")
@login_required
def delete_comment(comment_id: int) -> Response:
    comment = db.session.get(Comment, comment_id)
    if comment is None:
        abort(404)
    try:
        service.delete_comment(comment, actor=current_user)
    except service.PermissionDeniedError:
        abort(403)
    flash("Comment removed.", "info")
    return redirect(url_for("knowledge_vault.detail", slug=comment.item.slug) + "#comments")


@bp.post("/bulk")
@login_required
def bulk() -> Response:
    form = BulkActionForm()
    if not form.validate_on_submit() or not form.item_ids.data:
        flash("Select at least one item and an action.", "warning")
        return redirect(url_for("knowledge_vault.index"))
    count = service.bulk_action(form.action.data, form.item_ids.data, actor=current_user)
    flash(f"Applied “{form.action.data.replace('_', ' ')}” to {count} item(s).", "success")
    return redirect(request.referrer or url_for("knowledge_vault.index"))


@bp.get("/<slug>/export.<fmt>")
def export(slug: str, fmt: str) -> Response:
    if fmt not in {"json", "md"}:
        abort(404)
    item = _item_or_404(slug)
    body, mimetype = service.export_item(item, fmt)
    response = Response(body, mimetype=mimetype)
    response.headers["Content-Disposition"] = f'attachment; filename="{item.slug}.{fmt}"'
    return response


@bp.get("/categories")
def categories() -> str:
    rows = db.session.execute(
        select(Category, func.count(KnowledgeItem.id))
        .outerjoin(KnowledgeItem, KnowledgeItem.category_id == Category.id)
        .group_by(Category.id)
        .order_by(Category.name)
    ).all()
    return render_template("vault/categories.html", rows=rows)

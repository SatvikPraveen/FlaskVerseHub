from __future__ import annotations

from flask import abort, flash, jsonify, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy import select
from werkzeug.wrappers import Response

from app.auth.decorators import admin_required
from app.dashboard import analytics, bp
from app.extensions import db
from app.models import Bookmark, KnowledgeItem, Notification
from app.utils.pagination import page_args, paginate


@bp.get("/")
@login_required
def index() -> str:
    summary = analytics.user_summary(current_user)
    recent_items = (
        current_user.knowledge_items.order_by(KnowledgeItem.updated_at.desc()).limit(6).all()
    )
    bookmarks = db.session.scalars(
        select(KnowledgeItem)
        .join(Bookmark, Bookmark.item_id == KnowledgeItem.id)
        .where(Bookmark.user_id == current_user.id)
        .order_by(Bookmark.created_at.desc())
        .limit(6)
    ).all()
    notifications = (
        current_user.notifications.order_by(Notification.created_at.desc()).limit(8).all()
    )
    activity = analytics.recent_activity(10, user=current_user)
    popular = analytics.most_viewed(5, user=current_user)
    return render_template(
        "dashboard/index.html",
        summary=summary,
        recent_items=recent_items,
        bookmarks=bookmarks,
        notifications=notifications,
        activity=activity,
        popular=popular,
    )


@bp.get("/analytics")
@login_required
@admin_required
def analytics_page() -> str:
    return render_template("dashboard/analytics.html", metrics=analytics.admin_metrics())


@bp.get("/analytics.json")
@login_required
@admin_required
def analytics_json() -> Response:
    return jsonify(analytics.admin_metrics())


@bp.get("/notifications")
@login_required
def notifications() -> str:
    page, per_page = page_args()
    stmt = (
        select(Notification)
        .where(Notification.user_id == current_user.id)
        .order_by(Notification.created_at.desc())
    )
    if request.args.get("unread"):
        stmt = stmt.where(Notification.is_read.is_(False))
    return render_template("dashboard/notifications.html", page=paginate(stmt, page, per_page))


@bp.post("/notifications/<int:notification_id>/read")
@login_required
def mark_read(notification_id: int) -> Response:
    note = db.session.get(Notification, notification_id)
    if note is None or note.user_id != current_user.id:
        abort(404)
    note.mark_read()
    db.session.commit()
    if request.accept_mimetypes.best == "application/json" or request.is_json:
        return jsonify(
            {"ok": True, "unread": current_user.notifications.filter_by(is_read=False).count()}
        )
    return redirect(note.link or url_for("dashboard.notifications"))


@bp.post("/notifications/read-all")
@login_required
def mark_all_read() -> Response:
    for note in current_user.notifications.filter_by(is_read=False).all():
        note.mark_read()
    db.session.commit()
    flash("All notifications marked as read.", "success")
    return redirect(url_for("dashboard.notifications"))


@bp.get("/activity")
@login_required
def activity() -> str:
    page, per_page = page_args()
    from app.models import Activity

    stmt = select(Activity).order_by(Activity.created_at.desc())
    if not current_user.is_admin:
        stmt = stmt.where(Activity.user_id == current_user.id)
    return render_template("dashboard/activity.html", page=paginate(stmt, page, per_page))

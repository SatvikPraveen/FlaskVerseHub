from __future__ import annotations

from urllib.parse import urljoin, urlparse

from flask import (
    abort,
    current_app,
    flash,
    redirect,
    render_template,
    request,
    url_for,
)
from flask_login import current_user, login_required, login_user, logout_user
from sqlalchemy import select
from werkzeug.wrappers import Response

from app.auth import bp, service
from app.auth.forms import (
    ApiKeyForm,
    ChangePasswordForm,
    DeleteAccountForm,
    LoginForm,
    PasswordResetForm,
    PasswordResetRequestForm,
    ProfileForm,
    RegistrationForm,
)
from app.extensions import db, limiter
from app.models import ApiKey, KnowledgeItem
from app.services.activity import record_activity


def _is_safe_url(target: str | None) -> bool:
    if not target:
        return False
    ref = urlparse(request.host_url)
    test = urlparse(urljoin(request.host_url, target))
    return test.scheme in {"http", "https"} and ref.netloc == test.netloc


def _redirect_back(default: str = "main.index") -> Response:
    target = request.args.get("next")
    return redirect(target if _is_safe_url(target) else url_for(default))


def _auth_limit() -> str:
    return str(current_app.config.get("RATELIMIT_AUTH", "10 per minute"))


@bp.route("/register", methods=["GET", "POST"])
@limiter.limit(_auth_limit, methods=["POST"])
def register() -> Response | str:
    if current_user.is_authenticated:
        return redirect(url_for("main.index"))
    form = RegistrationForm()
    if form.validate_on_submit():
        try:
            user = service.register_user(
                form.username.data or "",
                form.email.data or "",
                form.password.data or "",
                first_name=form.first_name.data or None,
                last_name=form.last_name.data or None,
            )
        except service.DuplicateAccountError as exc:
            getattr(form, str(exc)).errors.append(f"That {exc} is already taken.")
        else:
            login_user(user)
            flash("Welcome aboard! Check your inbox to verify your email address.", "success")
            return redirect(url_for("main.index"))
    return render_template("auth/register.html", form=form)


@bp.route("/login", methods=["GET", "POST"])
@limiter.limit(_auth_limit, methods=["POST"])
def login() -> Response | str:
    if current_user.is_authenticated:
        return _redirect_back()
    form = LoginForm()
    if form.validate_on_submit():
        result = service.authenticate(form.identifier.data or "", form.password.data or "")
        if result.ok and result.user is not None:
            login_user(result.user, remember=bool(form.remember_me.data))
            flash(f"Signed in as {result.user.username}.", "success")
            return _redirect_back()
        if result.failure is service.LoginFailure.LOCKED:
            flash("Too many failed attempts. The account is temporarily locked.", "danger")
        elif result.failure is service.LoginFailure.INACTIVE:
            flash("This account is disabled.", "danger")
        else:
            flash("Invalid username or password.", "danger")
    return render_template("auth/login.html", form=form)


@bp.post("/logout")
@login_required
def logout() -> Response:
    record_activity("user.logout", user=current_user, commit=True)
    logout_user()
    flash("You have been signed out.", "info")
    return redirect(url_for("main.index"))


@bp.route("/profile", methods=["GET", "POST"])
@login_required
def profile() -> Response | str:
    form = ProfileForm(obj=current_user)
    if request.method == "GET":
        form.email_notifications.data = bool(current_user.preference("email_notifications", True))
    if form.validate_on_submit():
        current_user.first_name = form.first_name.data or None
        current_user.last_name = form.last_name.data or None
        current_user.bio = form.bio.data or None
        current_user.website = form.website.data or None
        current_user.location = form.location.data or None
        current_user.theme = form.theme.data or "light"
        current_user.preferences = {
            **(current_user.preferences or {}),
            "email_notifications": bool(form.email_notifications.data),
        }
        record_activity("user.profile_updated", user=current_user, commit=True)
        flash("Profile saved.", "success")
        return redirect(url_for("auth.profile"))
    item_count = current_user.knowledge_items.count()
    recent_items = (
        current_user.knowledge_items.order_by(KnowledgeItem.updated_at.desc()).limit(5).all()
    )
    return render_template(
        "auth/profile.html", form=form, item_count=item_count, recent_items=recent_items
    )


@bp.route("/password/change", methods=["GET", "POST"])
@login_required
def change_password() -> Response | str:
    form = ChangePasswordForm()
    if form.validate_on_submit():
        if service.change_password(
            current_user, form.current_password.data or "", form.new_password.data or ""
        ):
            flash("Password changed.", "success")
            return redirect(url_for("auth.profile"))
        form.current_password.errors.append("Current password is incorrect.")
    return render_template("auth/change_password.html", form=form)


@bp.route("/password/reset", methods=["GET", "POST"])
@limiter.limit(_auth_limit, methods=["POST"])
def reset_password_request() -> Response | str:
    if current_user.is_authenticated:
        return redirect(url_for("auth.profile"))
    form = PasswordResetRequestForm()
    if form.validate_on_submit():
        service.request_password_reset(form.identifier.data or "")
        # Same message whether or not the account exists (no user enumeration).
        flash("If that account exists, a reset link is on its way.", "info")
        return redirect(url_for("auth.login"))
    return render_template("auth/reset_request.html", form=form)


@bp.route("/password/reset/<token>", methods=["GET", "POST"])
def reset_password(token: str) -> Response | str:
    if current_user.is_authenticated:
        return redirect(url_for("auth.profile"))
    if service.user_for_reset_token(token) is None:
        flash("That reset link is invalid or has expired.", "danger")
        return redirect(url_for("auth.reset_password_request"))
    form = PasswordResetForm()
    if form.validate_on_submit():
        user = service.reset_password(token, form.password.data or "")
        if user is None:
            flash("That reset link is invalid or has expired.", "danger")
            return redirect(url_for("auth.reset_password_request"))
        flash("Password updated. You can sign in now.", "success")
        return redirect(url_for("auth.login"))
    return render_template("auth/reset_password.html", form=form, token=token)


@bp.get("/verify/<token>")
def verify_email(token: str) -> Response:
    user = service.verify_email(token)
    if user is None:
        flash("That verification link is invalid or has expired.", "danger")
    else:
        flash("Email verified. Thank you!", "success")
    return redirect(
        url_for("auth.profile") if current_user.is_authenticated else url_for("auth.login")
    )


@bp.post("/verify/resend")
@login_required
@limiter.limit("3 per hour")
def resend_verification() -> Response:
    if current_user.email_verified:
        flash("Your email is already verified.", "info")
    else:
        service.send_verification_email(current_user)
        flash("Verification email sent.", "success")
    return redirect(url_for("auth.profile"))


@bp.route("/api-keys", methods=["GET", "POST"])
@login_required
def api_keys() -> Response | str:
    form = ApiKeyForm()
    new_key: str | None = None
    if form.validate_on_submit():
        _, new_key = service.issue_api_key(
            current_user, form.name.data or "key", form.scopes.data or ["read"]
        )
        flash("API key created. Copy it now; it will not be shown again.", "warning")
        form = ApiKeyForm(formdata=None)
    keys = db.session.scalars(
        select(ApiKey).where(ApiKey.user_id == current_user.id).order_by(ApiKey.created_at.desc())
    ).all()
    return render_template("auth/api_keys.html", form=form, keys=keys, new_key=new_key)


@bp.post("/api-keys/<int:key_id>/revoke")
@login_required
def revoke_api_key(key_id: int) -> Response:
    if not service.revoke_api_key(current_user, key_id):
        abort(404)
    flash("API key revoked.", "info")
    return redirect(url_for("auth.api_keys"))


@bp.route("/account/delete", methods=["GET", "POST"])
@login_required
def delete_account() -> Response | str:
    form = DeleteAccountForm()
    if form.validate_on_submit():
        user = current_user._get_current_object()
        if service.delete_account(user, form.password.data or ""):
            logout_user()
            flash("Your account has been deleted.", "info")
            return redirect(url_for("main.index"))
        form.password.errors.append("Password is incorrect.")
    return render_template("auth/delete_account.html", form=form)

# File: app/auth/routes.py
# 🔐 Authentication Routes

from flask import render_template, request, redirect, url_for, flash, jsonify, current_app, session
from flask_login import login_user, logout_user, login_required, current_user
from urllib.parse import urlparse, urljoin
from datetime import datetime

from . import auth
from .forms import (
    LoginForm, RegistrationForm, ResetPasswordRequestForm, 
    ResetPasswordForm, ChangePasswordForm, ProfileForm,
    TwoFactorForm, AccountSettingsForm, DeleteAccountForm
)
from .jwt_utils import create_password_reset_token, verify_password_reset_token
from ..models import User, db
from ..utils.email_utils import send_email
from ..dashboard.events import track_activity


def is_safe_url(target):
    """Check if redirect URL is safe."""
    ref_url = urlparse(request.host_url)
    test_url = urlparse(urljoin(request.host_url, target))
    return test_url.scheme in ('http', 'https') and ref_url.netloc == test_url.netloc


@auth.route('/login', methods=['GET', 'POST'])
def login():
    """User login route."""
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.index'))
    
    form = LoginForm()
    
    if form.validate_on_submit():
        # Check if username or email
        user = User.query.filter(
            (User.username == form.username.data.lower()) |
            (User.email == form.username.data.lower())
        ).first()
        
        if user and user.check_password(form.password.data):
            if not user.is_active:
                flash('Your account has been deactivated. Please contact support.', 'error')
                return render_template('auth/login.html', form=form)
            
            # Update last login
            user.last_login = datetime.utcnow()
            db.session.commit()
            
            # Login user
            login_user(user, remember=form.remember_me.data)
            
            # Track activity
            track_activity('user_login', user=user)
            
            flash(f'Welcome back, {user.username}!', 'success')
            
            # Redirect to next page or dashboard
            next_page = request.args.get('next')
            if not next_page or not is_safe_url(next_page):
                next_page = url_for('dashboard.index')
            
            return redirect(next_page)
        else:
            flash('Invalid username/email or password.', 'error')
    
    return render_template('auth/login.html', form=form)


@auth.route('/logout')
@login_required
def logout():
    """User logout route."""
    # Track activity before logout
    track_activity('user_logout', user=current_user)
    
    flash(f'You have been logged out. See you next time!', 'info')
    logout_user()
    return redirect(url_for('auth.login'))


@auth.route('/register', methods=['GET', 'POST'])
def register():
    """User registration route."""
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.index'))
    
    form = RegistrationForm()
    
    if form.validate_on_submit():
        try:
            user = User(
                username=form.username.data.lower(),
                email=form.email.data.lower(),
                first_name=form.first_name.data,
                last_name=form.last_name.data
            )
            user.set_password(form.password.data)
            
            db.session.add(user)
            db.session.commit()
            
            flash('Registration successful! You can now log in.', 'success')
            return redirect(url_for('auth.login'))
        
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f'Registration error: {e}')
            flash('Registration failed. Please try again.', 'error')
    
    return render_template('auth/register.html', form=form)


@auth.route('/reset-password-request', methods=['GET', 'POST'])
def reset_password_request():
    """Password reset request route."""
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.index'))
    
    form = ResetPasswordRequestForm()
    
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data.lower()).first()
        
        if user:
            token = create_password_reset_token(user)
            
            # Send password reset email
            try:
                send_email(
                    to=user.email,
                    subject='Password Reset Request',
                    template='auth/email/reset_password',
                    user=user,
                    token=token,
                    reset_url=url_for('auth.reset_password', token=token, _external=True)
                )
                
                flash('A password reset link has been sent to your email.', 'info')
            except Exception as e:
                current_app.logger.error(f'Failed to send password reset email: {e}')
                flash('Failed to send reset email. Please try again later.', 'error')
        else:
            # Don't reveal if email exists or not for security
            flash('If that email exists in our system, a reset link has been sent.', 'info')
        
        return redirect(url_for('auth.login'))
    
    return render_template('auth/reset_password_request.html', form=form)


@auth.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    """Password reset route."""
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.index'))
    
    payload, error = verify_password_reset_token(token)
    
    if error or not payload:
        flash('Invalid or expired reset token.', 'error')
        return redirect(url_for('auth.reset_password_request'))
    
    user = User.query.get(payload['user_id'])
    
    if not user:
        flash('Invalid reset token.', 'error')
        return redirect(url_for('auth.reset_password_request'))
    
    form = ResetPasswordForm()
    
    if form.validate_on_submit():
        try:
            user.set_password(form.password.data)
            db.session.commit()
            
            flash('Your password has been reset successfully.', 'success')
            return redirect(url_for('auth.login'))
        
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f'Password reset error: {e}')
            flash('Failed to reset password. Please try again.', 'error')
    
    return render_template('auth/reset_password.html', form=form)


@auth.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    """User profile route."""
    form = ProfileForm(
        original_username=current_user.username,
        original_email=current_user.email,
        obj=current_user
    )
    
    if form.validate_on_submit():
        try:
            current_user.username = form.username.data.lower()
            current_user.email = form.email.data.lower()
            current_user.first_name = form.first_name.data
            current_user.last_name = form.last_name.data
            current_user.bio = form.bio.data
            current_user.updated_at = datetime.utcnow()
            
            db.session.commit()
            flash('Your profile has been updated.', 'success')
            return redirect(url_for('auth.profile'))
        
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f'Profile update error: {e}')
            flash('Failed to update profile. Please try again.', 'error')
    
    return render_template('auth/profile.html', form=form)


@auth.route('/change-password', methods=['GET', 'POST'])
@login_required
def change_password():
    """Change password route."""
    form = ChangePasswordForm()
    
    if form.validate_on_submit():
        if not current_user.check_password(form.current_password.data):
            flash('Current password is incorrect.', 'error')
            return render_template('auth/change_password.html', form=form)
        
        try:
            current_user.set_password(form.new_password.data)
            db.session.commit()
            
            flash('Your password has been changed successfully.', 'success')
            return redirect(url_for('auth.profile'))
        
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f'Password change error: {e}')
            flash('Failed to change password. Please try again.', 'error')
    
    return render_template('auth/change_password.html', form=form)


@auth.route('/settings', methods=['GET', 'POST'])
@login_required
def settings():
    """Account settings route."""
    form = AccountSettingsForm(obj=current_user)
    
    if form.validate_on_submit():
        try:
            # Update user settings
            current_user.email_notifications = form.email_notifications.data
            current_user.marketing_emails = form.marketing_emails.data
            current_user.public_profile = form.public_profile.data
            current_user.show_email = form.show_email.data
            current_user.timezone = form.timezone.data
            current_user.language = form.language.data
            current_user.updated_at = datetime.utcnow()
            
            db.session.commit()
            flash('Your settings have been updated.', 'success')
            return redirect(url_for('auth.settings'))
        
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f'Settings update error: {e}')
            flash('Failed to update settings. Please try again.', 'error')
    
    return render_template('auth/settings.html', form=form)


@auth.route('/delete-account', methods=['GET', 'POST'])
@login_required
def delete_account():
    """Delete account route."""
    form = DeleteAccountForm()
    
    if form.validate_on_submit():
        if not current_user.check_password(form.password.data):
            flash('Incorrect password.', 'error')
            return render_template('auth/delete_account.html', form=form)
        
        try:
            # Store user data for cleanup
            user_id = current_user.id
            username = current_user.username
            
            # Delete user and related data
            db.session.delete(current_user)
            db.session.commit()
            
            # Logout user
            logout_user()
            
            flash('Your account has been deleted successfully.', 'info')
            current_app.logger.info(f'User account deleted: {username} (ID: {user_id})')
            
            return redirect(url_for('auth.register'))
        
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f'Account deletion error: {e}')
            flash('Failed to delete account. Please try again.', 'error')
    
    return render_template('auth/delete_account.html', form=form)


# API endpoints
@auth.route('/api/login', methods=['POST'])
def api_login():
    """API login endpoint."""
    from .jwt_utils import create_access_token, create_refresh_token
    
    data = request.get_json()
    
    if not data or not data.get('username') or not data.get('password'):
        return jsonify({'error': 'Username and password required'}), 400
    
    user = User.query.filter(
        (User.username == data['username'].lower()) |
        (User.email == data['username'].lower())
    ).first()
    
    if not user or not user.check_password(data['password']):
        return jsonify({'error': 'Invalid credentials'}), 401
    
    if not user.is_active:
        return jsonify({'error': 'Account deactivated'}), 401
    
    # Update last login
    user.last_login = datetime.utcnow()
    db.session.commit()
    
    # Generate tokens
    access_token = create_access_token(user)
    refresh_token = create_refresh_token(user)
    
    return jsonify({
        'access_token': access_token,
        'refresh_token': refresh_token,
        'user': {
            'id': user.id,
            'username': user.username,
            'email': user.email,
            'is_admin': user.is_admin
        }
    })


@auth.route('/api/refresh', methods=['POST'])
def api_refresh():
    """API token refresh endpoint."""
    from .jwt_utils import JWTManager
    
    data = request.get_json()
    refresh_token = data.get('refresh_token')
    
    if not refresh_token:
        return jsonify({'error': 'Refresh token required'}), 400
    
    new_token, error = JWTManager.refresh_access_token(refresh_token)
    
    if error:
        return jsonify({'error': error}), 401
    
    return jsonify({'access_token': new_token})


@auth.route('/api/logout', methods=['POST'])
@login_required
def api_logout():
    """API logout endpoint."""
    # In a full implementation, you'd revoke tokens here
    return jsonify({'message': 'Logged out successfully'})


@auth.route('/api/profile', methods=['GET'])
@login_required
def api_profile():
    """API get profile endpoint."""
    return jsonify({
        'user': {
            'id': current_user.id,
            'username': current_user.username,
            'email': current_user.email,
            'first_name': current_user.first_name,
            'last_name': current_user.last_name,
            'bio': current_user.bio,
            'is_admin': current_user.is_admin,
            'created_at': current_user.created_at.isoformat(),
            'last_login': current_user.last_login.isoformat() if current_user.last_login else None
        }
    })


@auth.route('/api/profile', methods=['PUT'])
@login_required
def api_update_profile():
    """API update profile endpoint."""
    data = request.get_json()
    
    if not data:
        return jsonify({'error': 'No data provided'}), 400
    
    try:
        if 'first_name' in data:
            current_user.first_name = data['first_name']
        if 'last_name' in data:
            current_user.last_name = data['last_name']
        if 'bio' in data:
            current_user.bio = data['bio']
        
        current_user.updated_at = datetime.utcnow()
        db.session.commit()
        
        return jsonify({'message': 'Profile updated successfully'})
    
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f'API profile update error: {e}')
        return jsonify({'error': 'Failed to update profile'}), 500
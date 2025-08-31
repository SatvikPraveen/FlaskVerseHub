# File: app/auth/forms.py
# 🔐 Authentication Forms

from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, BooleanField, TextAreaField, SelectField
from wtforms.validators import DataRequired, Email, EqualTo, Length, ValidationError, Optional
from wtforms.fields import EmailField

from ..models import User


class LoginForm(FlaskForm):
    """User login form."""
    
    username = StringField(
        'Username or Email',
        validators=[
            DataRequired(message='Username or email is required'),
            Length(min=3, max=80, message='Username must be between 3 and 80 characters')
        ],
        render_kw={'placeholder': 'Enter your username or email', 'autocomplete': 'username'}
    )
    
    password = PasswordField(
        'Password',
        validators=[
            DataRequired(message='Password is required')
        ],
        render_kw={'placeholder': 'Enter your password', 'autocomplete': 'current-password'}
    )
    
    remember_me = BooleanField('Remember me', default=False)


class RegistrationForm(FlaskForm):
    """User registration form."""
    
    username = StringField(
        'Username',
        validators=[
            DataRequired(message='Username is required'),
            Length(min=3, max=80, message='Username must be between 3 and 80 characters')
        ],
        render_kw={'placeholder': 'Choose a unique username', 'autocomplete': 'username'}
    )
    
    email = EmailField(
        'Email',
        validators=[
            DataRequired(message='Email is required'),
            Email(message='Please enter a valid email address')
        ],
        render_kw={'placeholder': 'your@email.com', 'autocomplete': 'email'}
    )
    
    first_name = StringField(
        'First Name',
        validators=[
            Optional(),
            Length(max=100, message='First name cannot exceed 100 characters')
        ],
        render_kw={'placeholder': 'Your first name', 'autocomplete': 'given-name'}
    )
    
    last_name = StringField(
        'Last Name',
        validators=[
            Optional(),
            Length(max=100, message='Last name cannot exceed 100 characters')
        ],
        render_kw={'placeholder': 'Your last name', 'autocomplete': 'family-name'}
    )
    
    password = PasswordField(
        'Password',
        validators=[
            DataRequired(message='Password is required'),
            Length(min=8, message='Password must be at least 8 characters long')
        ],
        render_kw={'placeholder': 'Create a strong password', 'autocomplete': 'new-password'}
    )
    
    confirm_password = PasswordField(
        'Confirm Password',
        validators=[
            DataRequired(message='Please confirm your password'),
            EqualTo('password', message='Passwords must match')
        ],
        render_kw={'placeholder': 'Confirm your password', 'autocomplete': 'new-password'}
    )
    
    agree_terms = BooleanField(
        'I agree to the Terms of Service and Privacy Policy',
        validators=[DataRequired(message='You must agree to the terms to register')]
    )
    
    def validate_username(self, username):
        """Check if username is already taken."""
        user = User.query.filter_by(username=username.data.lower()).first()
        if user:
            raise ValidationError('This username is already taken. Please choose a different one.')
    
    def validate_email(self, email):
        """Check if email is already registered."""
        user = User.query.filter_by(email=email.data.lower()).first()
        if user:
            raise ValidationError('This email is already registered. Please use a different email or try logging in.')


class ResetPasswordRequestForm(FlaskForm):
    """Password reset request form."""
    
    email = EmailField(
        'Email',
        validators=[
            DataRequired(message='Email is required'),
            Email(message='Please enter a valid email address')
        ],
        render_kw={'placeholder': 'Enter your registered email', 'autocomplete': 'email'}
    )
    
    def validate_email(self, email):
        """Check if email exists in system."""
        user = User.query.filter_by(email=email.data.lower()).first()
        if not user:
            raise ValidationError('No account found with this email address.')


class ResetPasswordForm(FlaskForm):
    """Password reset form."""
    
    password = PasswordField(
        'New Password',
        validators=[
            DataRequired(message='Password is required'),
            Length(min=8, message='Password must be at least 8 characters long')
        ],
        render_kw={'placeholder': 'Enter your new password', 'autocomplete': 'new-password'}
    )
    
    confirm_password = PasswordField(
        'Confirm New Password',
        validators=[
            DataRequired(message='Please confirm your new password'),
            EqualTo('password', message='Passwords must match')
        ],
        render_kw={'placeholder': 'Confirm your new password', 'autocomplete': 'new-password'}
    )


class ChangePasswordForm(FlaskForm):
    """Change password form for authenticated users."""
    
    current_password = PasswordField(
        'Current Password',
        validators=[
            DataRequired(message='Current password is required')
        ],
        render_kw={'placeholder': 'Enter your current password', 'autocomplete': 'current-password'}
    )
    
    new_password = PasswordField(
        'New Password',
        validators=[
            DataRequired(message='New password is required'),
            Length(min=8, message='Password must be at least 8 characters long')
        ],
        render_kw={'placeholder': 'Enter your new password', 'autocomplete': 'new-password'}
    )
    
    confirm_password = PasswordField(
        'Confirm New Password',
        validators=[
            DataRequired(message='Please confirm your new password'),
            EqualTo('new_password', message='Passwords must match')
        ],
        render_kw={'placeholder': 'Confirm your new password', 'autocomplete': 'new-password'}
    )


class ProfileForm(FlaskForm):
    """User profile form."""
    
    username = StringField(
        'Username',
        validators=[
            DataRequired(message='Username is required'),
            Length(min=3, max=80, message='Username must be between 3 and 80 characters')
        ],
        render_kw={'placeholder': 'Your username'}
    )
    
    email = EmailField(
        'Email',
        validators=[
            DataRequired(message='Email is required'),
            Email(message='Please enter a valid email address')
        ],
        render_kw={'placeholder': 'your@email.com'}
    )
    
    first_name = StringField(
        'First Name',
        validators=[
            Optional(),
            Length(max=100, message='First name cannot exceed 100 characters')
        ],
        render_kw={'placeholder': 'Your first name'}
    )
    
    last_name = StringField(
        'Last Name',
        validators=[
            Optional(),
            Length(max=100, message='Last name cannot exceed 100 characters')
        ],
        render_kw={'placeholder': 'Your last name'}
    )
    
    bio = TextAreaField(
        'Bio',
        validators=[
            Optional(),
            Length(max=500, message='Bio cannot exceed 500 characters')
        ],
        render_kw={'placeholder': 'Tell us about yourself...', 'rows': 4}
    )
    
    def __init__(self, original_username=None, original_email=None, *args, **kwargs):
        super(ProfileForm, self).__init__(*args, **kwargs)
        self.original_username = original_username
        self.original_email = original_email
    
    def validate_username(self, username):
        """Check if username is available (excluding current user)."""
        if username.data != self.original_username:
            user = User.query.filter_by(username=username.data.lower()).first()
            if user:
                raise ValidationError('This username is already taken.')
    
    def validate_email(self, email):
        """Check if email is available (excluding current user)."""
        if email.data != self.original_email:
            user = User.query.filter_by(email=email.data.lower()).first()
            if user:
                raise ValidationError('This email is already registered.')


class TwoFactorSetupForm(FlaskForm):
    """Two-factor authentication setup form."""
    
    token = StringField(
        'Verification Code',
        validators=[
            DataRequired(message='Verification code is required'),
            Length(min=6, max=6, message='Verification code must be 6 digits')
        ],
        render_kw={'placeholder': '123456', 'maxlength': 6, 'autocomplete': 'one-time-code'}
    )


class TwoFactorForm(FlaskForm):
    """Two-factor authentication verification form."""
    
    token = StringField(
        'Authentication Code',
        validators=[
            DataRequired(message='Authentication code is required'),
            Length(min=6, max=6, message='Authentication code must be 6 digits')
        ],
        render_kw={'placeholder': '123456', 'maxlength': 6, 'autocomplete': 'one-time-code'}
    )
    
    remember_device = BooleanField(
        'Remember this device for 30 days',
        default=False
    )


class AccountSettingsForm(FlaskForm):
    """Account settings form."""
    
    email_notifications = BooleanField(
        'Email Notifications',
        default=True,
        description='Receive notifications via email'
    )
    
    marketing_emails = BooleanField(
        'Marketing Emails',
        default=False,
        description='Receive marketing and promotional emails'
    )
    
    public_profile = BooleanField(
        'Public Profile',
        default=True,
        description='Make your profile visible to other users'
    )
    
    show_email = BooleanField(
        'Show Email',
        default=False,
        description='Display your email on your public profile'
    )
    
    timezone = SelectField(
        'Timezone',
        choices=[
            ('UTC', 'UTC'),
            ('US/Eastern', 'Eastern Time'),
            ('US/Central', 'Central Time'),
            ('US/Mountain', 'Mountain Time'),
            ('US/Pacific', 'Pacific Time'),
            ('Europe/London', 'London'),
            ('Europe/Paris', 'Paris'),
            ('Europe/Berlin', 'Berlin'),
            ('Asia/Tokyo', 'Tokyo'),
            ('Asia/Shanghai', 'Shanghai'),
            ('Australia/Sydney', 'Sydney')
        ],
        default='UTC'
    )
    
    language = SelectField(
        'Language',
        choices=[
            ('en', 'English'),
            ('es', 'Español'),
            ('fr', 'Français'),
            ('de', 'Deutsch'),
            ('zh', '中文')
        ],
        default='en'
    )


class DeleteAccountForm(FlaskForm):
    """Account deletion confirmation form."""
    
    password = PasswordField(
        'Current Password',
        validators=[
            DataRequired(message='Password is required to delete account')
        ],
        render_kw={'placeholder': 'Enter your current password'}
    )
    
    confirmation = StringField(
        'Type "DELETE" to confirm',
        validators=[
            DataRequired(message='Please type DELETE to confirm'),
        ],
        render_kw={'placeholder': 'Type DELETE in capital letters'}
    )
    
    def validate_confirmation(self, confirmation):
        """Validate deletion confirmation."""
        if confirmation.data != 'DELETE':
            raise ValidationError('You must type "DELETE" exactly to confirm account deletion.')


class AdminUserForm(FlaskForm):
    """Admin form for managing users."""
    
    username = StringField(
        'Username',
        validators=[
            DataRequired(message='Username is required'),
            Length(min=3, max=80)
        ]
    )
    
    email = EmailField(
        'Email',
        validators=[
            DataRequired(message='Email is required'),
            Email(message='Please enter a valid email address')
        ]
    )
    
    first_name = StringField(
        'First Name',
        validators=[Optional(), Length(max=100)]
    )
    
    last_name = StringField(
        'Last Name',
        validators=[Optional(), Length(max=100)]
    )
    
    is_active = BooleanField('Account Active', default=True)
    is_admin = BooleanField('Administrator', default=False)
    
    def __init__(self, user=None, *args, **kwargs):
        super(AdminUserForm, self).__init__(*args, **kwargs)
        self.user = user
    
    def validate_username(self, username):
        """Check username availability."""
        if self.user and username.data == self.user.username:
            return
        
        user = User.query.filter_by(username=username.data.lower()).first()
        if user:
            raise ValidationError('Username already exists.')
    
    def validate_email(self, email):
        """Check email availability."""
        if self.user and email.data == self.user.email:
            return
        
        user = User.query.filter_by(email=email.data.lower()).first()
        if user:
            raise ValidationError('Email already registered.')
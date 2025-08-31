# File: FlaskVerseHub/app/extensions.py

from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager
from flask_caching import Cache
from flask_mail import Mail
from flask_socketio import SocketIO
from flask_jwt_extended import JWTManager
from flask_cors import CORS
from flask_wtf.csrf import CSRFProtect
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

# Initialize extensions
db = SQLAlchemy()
migrate = Migrate()
login_manager = LoginManager()
cache = Cache()
mail = Mail()
socketio = SocketIO()
jwt = JWTManager()
cors = CORS()
csrf = CSRFProtect()
limiter = Limiter(key_func=get_remote_address)
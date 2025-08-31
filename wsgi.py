# File: FlaskVerseHub/wsgi.py

import os
from app import create_app

# Get configuration from environment
config_name = os.getenv('FLASK_CONFIG', 'production')

# Create application instance
application = create_app(config_name)

if __name__ == "__main__":
    application.run()
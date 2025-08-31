"""
Error Handling Blueprint
Demonstrates Flask error handling and custom error pages
"""
from flask import Blueprint

bp = Blueprint('errors', __name__, 
               template_folder='templates')

from app.errors import handlers

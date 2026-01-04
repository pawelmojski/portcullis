#!/usr/bin/env python3
"""
Jumphost Web GUI - Main Flask Application
Flask-based web interface for managing SSH/RDP jumphost access control.
"""

import os
import sys
from datetime import datetime
from flask import Flask, render_template, redirect, url_for, flash, request
from flask_login import LoginManager, login_required, current_user

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from src.core.database import SessionLocal, User, Server, ServerGroup, AccessPolicy, AuditLog
from src.core.access_control_v2 import AccessControlEngineV2

# Initialize Flask app
app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'postgresql://jumphost_user:password@localhost/jumphost')

# Initialize Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'auth.login'
login_manager.login_message = 'Please log in to access the Jumphost Web GUI.'

# Initialize Access Control Engine
access_control = AccessControlEngineV2()

@login_manager.user_loader
def load_user(user_id):
    """Load user for Flask-Login"""
    db = SessionLocal()
    try:
        user = db.query(User).get(int(user_id))
        if user:
            # Merge user into current session to avoid detached instance
            db.expunge(user)
        return user
    finally:
        db.close()

# Database session management
@app.before_request
def before_request():
    """Create database session before each request"""
    from flask import g
    g.db = SessionLocal()

@app.teardown_request
def teardown_request(exception=None):
    """Close database session after each request"""
    from flask import g
    db = g.pop('db', None)
    if db is not None:
        db.close()

# Template filters
@app.template_filter('datetime')
def format_datetime(value):
    """Format datetime for display"""
    if value is None:
        return ''
    return value.strftime('%Y-%m-%d %H:%M:%S')

@app.template_filter('date')
def format_date(value):
    """Format date for display"""
    if value is None:
        return ''
    return value.strftime('%Y-%m-%d')

@app.template_filter('timeago')
def format_timeago(value):
    """Format datetime as relative time ago"""
    if value is None:
        return ''
    from datetime import datetime, timezone
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    now = datetime.now(timezone.utc)
    diff = now - value
    
    seconds = diff.total_seconds()
    if seconds < 60:
        return 'just now'
    elif seconds < 3600:
        minutes = int(seconds / 60)
        return f'{minutes}m ago'
    elif seconds < 86400:
        hours = int(seconds / 3600)
        return f'{hours}h ago'
    else:
        days = int(seconds / 86400)
        return f'{days}d ago'

# Context processor for global template variables
@app.context_processor
def inject_globals():
    """Inject global variables into all templates"""
    return {
        'app_name': 'Jumphost Web GUI',
        'app_version': '1.0',
        'now': datetime.now()
    }

# Import and register blueprints
from blueprints.dashboard import dashboard_bp
from blueprints.users import users_bp
from blueprints.servers import servers_bp
from blueprints.groups import groups_bp
from blueprints.policies import policies_bp
from blueprints.monitoring import monitoring_bp
from blueprints.auth import auth_bp

app.register_blueprint(dashboard_bp, url_prefix='/')
app.register_blueprint(users_bp, url_prefix='/users')
app.register_blueprint(servers_bp, url_prefix='/servers')
app.register_blueprint(groups_bp, url_prefix='/groups')
app.register_blueprint(policies_bp, url_prefix='/policies')
app.register_blueprint(monitoring_bp, url_prefix='/monitoring')
app.register_blueprint(auth_bp, url_prefix='/auth')

# Favicon route (prevent 404 errors)
@app.route('/favicon.ico')
def favicon():
    """Serve favicon or return 204 No Content"""
    return '', 204

# Error handlers
@app.errorhandler(404)
def not_found(error):
    return render_template('errors/404.html'), 404

@app.errorhandler(500)
def internal_error(error):
    return render_template('errors/500.html'), 500

if __name__ == '__main__':
    # Development server
    app.run(host='0.0.0.0', port=5000, debug=True)

"""
Auth Blueprint - Authentication (placeholder for AAD integration)
"""
import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..')))

from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_user, logout_user, current_user
from werkzeug.security import check_password_hash
from src.core.database import SessionLocal, User

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    """Login page (placeholder - will be replaced with AAD)"""
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.index'))
    
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        # Placeholder authentication - replace with AAD
        if username == 'admin' and password == 'admin':
            db = SessionLocal()
            try:
                # Try to find or create admin user
                user = db.query(User).filter_by(username='admin').first()
                if not user:
                    user = User(username='admin', email='admin@jumphost.local', is_active=True)
                    db.add(user)
                    db.commit()
                    db.refresh(user)
                
                login_user(user, remember=True)
                flash('Logged in successfully!', 'success')
                
                next_page = request.args.get('next')
                return redirect(next_page or url_for('dashboard.index'))
            finally:
                db.close()
        else:
            flash('Invalid username or password', 'danger')
    
    return render_template('auth/login.html')

@auth_bp.route('/logout')
def logout():
    """Logout"""
    logout_user()
    flash('Logged out successfully!', 'info')
    return redirect(url_for('auth.login'))

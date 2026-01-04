"""
Users Blueprint - User and Source IP management
"""
from flask import Blueprint, render_template, g, request, redirect, url_for, flash, jsonify, abort
from flask_login import login_required
from datetime import datetime
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from src.core.database import SessionLocal, User, UserSourceIP

users_bp = Blueprint('users', __name__)

@users_bp.route('/')
@login_required
def index():
    """List all users"""
    db = g.db
    users = db.query(User).order_by(User.username).all()
    return render_template('users/index.html', users=users)

@users_bp.route('/view/<int:user_id>')
@login_required
def view(user_id):
    """View user details"""
    db = g.db
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        abort(404)
    return render_template('users/view.html', user=user)

@users_bp.route('/add', methods=['GET', 'POST'])
@login_required
def add():
    """Add new user"""
    if request.method == 'POST':
        db = g.db
        try:
            user = User(
                username=request.form['username'],
                full_name=request.form.get('full_name'),
                email=request.form.get('email')
            )
            db.add(user)
            db.commit()
            flash(f'User {user.username} added successfully!', 'success')
            return redirect(url_for('users.view', user_id=user.id))
        except Exception as e:
            db.rollback()
            flash(f'Error adding user: {str(e)}', 'danger')
    
    return render_template('users/add.html')

@users_bp.route('/edit/<int:user_id>', methods=['GET', 'POST'])
@login_required
def edit(user_id):
    """Edit user"""
    db = g.db
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        abort(404)
    
    if request.method == 'POST':
        try:
            user.full_name = request.form.get('full_name')
            user.email = request.form.get('email')
            db.commit()
            flash(f'User {user.username} updated successfully!', 'success')
            return redirect(url_for('users.view', user_id=user.id))
        except Exception as e:
            db.rollback()
            flash(f'Error updating user: {str(e)}', 'danger')
    
    return render_template('users/edit.html', user=user)

@users_bp.route('/delete/<int:user_id>', methods=['POST'])
@login_required
def delete(user_id):
    """Delete user"""
    db = g.db
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        abort(404)
    
    try:
        username = user.username
        db.delete(user)
        db.commit()
        flash(f'User {username} deleted successfully!', 'success')
    except Exception as e:
        db.rollback()
        flash(f'Error deleting user: {str(e)}', 'danger')
    
    return redirect(url_for('users.index'))

@users_bp.route('/<int:user_id>/ips/add', methods=['POST'])
@login_required
def add_ip(user_id):
    """Add source IP to user"""
    db = g.db
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        abort(404)
    
    try:
        source_ip = UserSourceIP(
            user_id=user.id,
            source_ip=request.form['source_ip'],
            label=request.form.get('label'),
            is_active=True
        )
        db.add(source_ip)
        db.commit()
        flash(f'Source IP {source_ip.source_ip} added successfully!', 'success')
    except Exception as e:
        db.rollback()
        flash(f'Error adding source IP: {str(e)}', 'danger')
    
    return redirect(url_for('users.view', user_id=user.id))

@users_bp.route('/<int:user_id>/ips/<int:ip_id>/delete', methods=['POST'])
@login_required
def delete_ip(user_id, ip_id):
    """Delete source IP from user"""
    db = g.db
    source_ip = db.query(UserSourceIP).filter(
        UserSourceIP.id == ip_id,
        UserSourceIP.user_id == user_id
    ).first()
    if not source_ip:
        abort(404)
    
    try:
        ip_address = source_ip.source_ip
        db.delete(source_ip)
        db.commit()
        flash(f'Source IP {ip_address} deleted successfully!', 'success')
    except Exception as e:
        db.rollback()
        flash(f'Error deleting source IP: {str(e)}', 'danger')
    
    return redirect(url_for('users.view', user_id=user_id))

@users_bp.route('/<int:user_id>/ips/<int:ip_id>/toggle', methods=['POST'])
@login_required
def toggle_ip(user_id, ip_id):
    """Toggle source IP active status"""
    db = g.db
    source_ip = db.query(UserSourceIP).filter(
        UserSourceIP.id == ip_id,
        UserSourceIP.user_id == user_id
    ).first()
    if not source_ip:
        abort(404)
    
    try:
        source_ip.is_active = not source_ip.is_active
        db.commit()
        status = 'activated' if source_ip.is_active else 'deactivated'
        flash(f'Source IP {source_ip.source_ip} {status}!', 'success')
    except Exception as e:
        db.rollback()
        flash(f'Error toggling source IP: {str(e)}', 'danger')
    
    return redirect(url_for('users.view', user_id=user_id))

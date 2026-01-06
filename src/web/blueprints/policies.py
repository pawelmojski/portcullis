"""
Access Policies Blueprint - Policy management
"""
from flask import Blueprint, render_template, g, request, redirect, url_for, flash, abort
from flask_login import login_required
from datetime import datetime, timedelta, time
import json

from src.core.database import AccessPolicy, User, UserSourceIP, Server, ServerGroup, PolicySSHLogin, UserGroup, PolicySchedule
from src.core.duration_parser import parse_duration, format_duration

policies_bp = Blueprint('policies', __name__)

@policies_bp.route('/')
@login_required
def index():
    """List all policies"""
    db = g.db
    
    # Filter parameters
    show_expired = request.args.get('show_expired', 'false') == 'true'
    user_filter = request.args.get('user')
    group_filter = request.args.get('group')
    
    query = db.query(AccessPolicy).filter(AccessPolicy.is_active == True)
    
    if not show_expired:
        now = datetime.utcnow()
        # Show policies that haven't expired yet (end_time > now OR end_time IS NULL)
        # This includes future grants (start_time > now) - they will be shown as "scheduled"
        query = query.filter(
            (AccessPolicy.end_time == None) | (AccessPolicy.end_time > now)
        )
    
    if user_filter:
        query = query.filter(AccessPolicy.user_id == int(user_filter))
    
    if group_filter:
        query = query.filter(AccessPolicy.user_group_id == int(group_filter))
    
    policies = query.order_by(AccessPolicy.created_at.desc()).all()
    users = db.query(User).order_by(User.username).all()
    user_groups = db.query(UserGroup).order_by(UserGroup.name).all()
    
    return render_template('policies/index.html', policies=policies, users=users,
                         user_groups=user_groups, show_expired=show_expired, 
                         user_filter=user_filter, group_filter=group_filter,
                         now=datetime.utcnow())

@policies_bp.route('/add', methods=['GET', 'POST'])
@login_required
def add():
    """Add new policy (grant wizard)"""
    db = g.db
    
    if request.method == 'POST':
        try:
            # Parse form data
            grant_type = request.form.get('grant_type', 'user')
            user_id = request.form.get('user_id')
            user_group_id = request.form.get('user_group_id')
            scope_type = request.form['scope_type']
            protocol = request.form.get('protocol') or None
            source_ip_id = request.form.get('source_ip_id')
            port_forwarding_allowed = request.form.get('port_forwarding_allowed') == 'on'
            
            # Validate: either user_id or user_group_id must be provided
            if grant_type == 'user' and not user_id:
                flash('User is required', 'danger')
                return redirect(url_for('policies.add'))
            if grant_type == 'group' and not user_group_id:
                flash('User group is required', 'danger')
                return redirect(url_for('policies.add'))
            
            # Parse start_time (optional, default to now)
            start_time_str = request.form.get('start_time')
            if start_time_str:
                # Parse HTML5 datetime-local format (YYYY-MM-DDTHH:MM)
                start_time = datetime.strptime(start_time_str, '%Y-%m-%dT%H:%M')
            else:
                start_time = datetime.utcnow()
            
            # Calculate end_time based on duration_type
            duration_type = request.form.get('duration_type', 'duration')
            end_time = None
            
            if duration_type == 'duration':
                # Parse human-readable duration
                duration_text = request.form.get('duration_text', '').strip()
                
                if duration_text:
                    total_minutes = parse_duration(duration_text)
                    
                    if total_minutes is None:
                        flash(f'Invalid duration format: "{duration_text}". Examples: 30m, 2h, 1d, 1.5h, 2d12h', 'danger')
                        return redirect(url_for('policies.add'))
                    
                    if total_minutes > 0:
                        end_time = start_time + timedelta(minutes=total_minutes)
                    # else: permanent (end_time = None)
                # else: permanent (no duration specified)
                
            elif duration_type == 'absolute':
                # Specific start and end date/time
                absolute_start_time_str = request.form.get('absolute_start_time')
                if absolute_start_time_str:
                    start_time = datetime.strptime(absolute_start_time_str, '%Y-%m-%dT%H:%M')
                # else: start_time already set to utcnow() or from form
                
                end_time_str = request.form.get('end_time')
                if end_time_str:
                    end_time = datetime.strptime(end_time_str, '%Y-%m-%dT%H:%M')
                else:
                    flash('End time is required when using absolute date/time', 'danger')
                    return redirect(url_for('policies.add'))
            
            # duration_type == 'permanent': end_time remains None
            
            # Create policy
            policy = AccessPolicy(
                user_id=int(user_id) if user_id else None,
                user_group_id=int(user_group_id) if user_group_id else None,
                source_ip_id=int(source_ip_id) if source_ip_id else None,
                scope_type=scope_type,
                protocol=protocol,
                port_forwarding_allowed=port_forwarding_allowed,
                is_active=True,
                start_time=start_time,
                end_time=end_time
            )
            
            # Set target based on scope
            if scope_type == 'group':
                policy.target_group_id = int(request.form['target_group_id'])
            elif scope_type in ['server', 'service']:
                policy.target_server_id = int(request.form['target_server_id'])
            
            db.add(policy)
            db.flush()  # Get policy ID
            
            # Add SSH logins if specified
            ssh_logins = request.form.get('ssh_logins', '').strip()
            if ssh_logins:
                for login in ssh_logins.split(','):
                    login = login.strip()
                    if login:
                        ssh_login = PolicySSHLogin(
                            policy_id=policy.id,
                            allowed_login=login
                        )
                        db.add(ssh_login)
            
            # Add schedules if enabled
            use_schedules = request.form.get('use_schedules') == 'on'
            if use_schedules:
                policy.use_schedules = True
                schedules_json = request.form.get('schedules_json')
                if schedules_json:
                    try:
                        schedules = json.loads(schedules_json)
                        for schedule_data in schedules:
                            schedule = PolicySchedule(
                                policy_id=policy.id,
                                name=schedule_data['name'],
                                weekdays=schedule_data.get('weekdays'),
                                time_start=datetime.strptime(schedule_data['time_start'], '%H:%M').time() if schedule_data.get('time_start') else None,
                                time_end=datetime.strptime(schedule_data['time_end'], '%H:%M').time() if schedule_data.get('time_end') else None,
                                months=schedule_data.get('months'),
                                days_of_month=schedule_data.get('days_of_month'),
                                timezone=schedule_data.get('timezone', 'Europe/Warsaw'),
                                is_active=True
                            )
                            db.add(schedule)
                    except Exception as e:
                        db.rollback()
                        flash(f'Error parsing schedules: {str(e)}', 'danger')
                        return redirect(url_for('policies.add'))
            
            db.commit()
            flash('Access policy created successfully!', 'success')
            return redirect(url_for('policies.index'))
            
        except Exception as e:
            db.rollback()
            flash(f'Error creating policy: {str(e)}', 'danger')
    
    # GET request - show form
    users = db.query(User).order_by(User.username).all()
    user_groups = db.query(UserGroup).order_by(UserGroup.name).all()
    servers = db.query(Server).order_by(Server.name).all()
    groups = db.query(ServerGroup).order_by(ServerGroup.name).all()
    
    return render_template('policies/add.html', users=users, user_groups=user_groups, 
                         servers=servers, groups=groups)

@policies_bp.route('/revoke/<int:policy_id>', methods=['POST'])
@login_required
def revoke(policy_id):
    """Revoke policy - set end_time to now (immediate expiry)"""
    db = g.db
    policy = db.query(AccessPolicy).filter(AccessPolicy.id == policy_id).first()
    if not policy:
        abort(404)
    
    try:
        # Set end_time to now - policy expires immediately
        # Keep is_active=True (temporal expiry, not soft delete)
        policy.end_time = datetime.utcnow()
        db.commit()
        flash('Policy revoked successfully! Access expired immediately.', 'success')
    except Exception as e:
        db.rollback()
        flash(f'Error revoking policy: {str(e)}', 'danger')
    
    return redirect(url_for('policies.index'))

@policies_bp.route('/renew/<int:policy_id>', methods=['POST'])
@login_required
def renew(policy_id):
    """Renew policy - extend end_time by specified days"""
    db = g.db
    policy = db.query(AccessPolicy).filter(AccessPolicy.id == policy_id).first()
    if not policy:
        abort(404)
    
    try:
        days = int(request.form.get('days', 30))
        now = datetime.utcnow()
        
        # Extend end_time
        if policy.end_time:
            # If policy already expired, extend from now
            if policy.end_time < now:
                policy.end_time = now + timedelta(days=days)
                flash(f'Policy reactivated and extended for {days} days from now!', 'success')
            else:
                # If still active, extend from current end_time
                policy.end_time = policy.end_time + timedelta(days=days)
                flash(f'Policy extended for {days} days!', 'success')
        else:
            # If NULL (permanent), set end_time from now
            policy.end_time = now + timedelta(days=days)
            flash(f'Permanent policy converted to {days}-day grant!', 'success')
        
        db.commit()
    except ValueError:
        db.rollback()
        flash('Invalid number of days', 'danger')
    except Exception as e:
        db.rollback()
        flash(f'Error renewing policy: {str(e)}', 'danger')
    
    return redirect(url_for('policies.index'))

@policies_bp.route('/delete/<int:policy_id>', methods=['POST'])
@login_required
def delete(policy_id):
    """Delete policy permanently"""
    db = g.db
    policy = db.query(AccessPolicy).filter(AccessPolicy.id == policy_id).first()
    if not policy:
        abort(404)
    
    try:
        db.delete(policy)
        db.commit()
        flash('Policy deleted successfully!', 'success')
    except Exception as e:
        db.rollback()
        flash(f'Error deleting policy: {str(e)}', 'danger')
    
    return redirect(url_for('policies.index'))

@policies_bp.route('/api/user/<int:user_id>/ips')
@login_required
def api_user_ips(user_id):
    """API endpoint to get user's source IPs"""
    db = g.db
    ips = db.query(UserSourceIP).filter(UserSourceIP.user_id == user_id).all()
    return {
        'ips': [{'id': ip.id, 'ip': ip.source_ip, 'label': ip.label} for ip in ips]
    }

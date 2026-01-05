"""
Access Policies Blueprint - Policy management
"""
from flask import Blueprint, render_template, g, request, redirect, url_for, flash, abort
from flask_login import login_required
from datetime import datetime, timedelta

from src.core.database import AccessPolicy, User, UserSourceIP, Server, ServerGroup, PolicySSHLogin, UserGroup

policies_bp = Blueprint('policies', __name__)

@policies_bp.route('/')
@login_required
def index():
    """List all policies"""
    db = g.db
    
    # Filter parameters
    show_inactive = request.args.get('show_inactive', 'false') == 'true'
    user_filter = request.args.get('user')
    
    query = db.query(AccessPolicy)
    
    if not show_inactive:
        now = datetime.now()
        query = query.filter(
            AccessPolicy.is_active == True,
            (AccessPolicy.end_time == None) | (AccessPolicy.end_time > now)
        )
    
    if user_filter:
        query = query.filter(AccessPolicy.user_id == int(user_filter))
    
    policies = query.order_by(AccessPolicy.created_at.desc()).all()
    users = db.query(User).order_by(User.username).all()
    
    return render_template('policies/index.html', policies=policies, users=users,
                         show_inactive=show_inactive, user_filter=user_filter)

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
            duration_hours = request.form.get('duration_hours')
            source_ip_id = request.form.get('source_ip_id')
            port_forwarding_allowed = request.form.get('port_forwarding_allowed') == 'on'
            
            # Validate: either user_id or user_group_id must be provided
            if grant_type == 'user' and not user_id:
                flash('User is required', 'danger')
                return redirect(url_for('policies.add'))
            if grant_type == 'group' and not user_group_id:
                flash('User group is required', 'danger')
                return redirect(url_for('policies.add'))
            
            # Calculate end time (0 = permanent, >0 = hours)
            end_time = None
            if duration_hours and int(duration_hours) > 0:
                end_time = datetime.now() + timedelta(hours=int(duration_hours))
            
            # Create policy
            policy = AccessPolicy(
                user_id=int(user_id) if user_id else None,
                user_group_id=int(user_group_id) if user_group_id else None,
                source_ip_id=int(source_ip_id) if source_ip_id else None,
                scope_type=scope_type,
                protocol=protocol,
                port_forwarding_allowed=port_forwarding_allowed,
                is_active=True,
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
    """Revoke (deactivate) policy"""
    db = g.db
    policy = db.query(AccessPolicy).filter(AccessPolicy.id == policy_id).first()
    if not policy:
        abort(404)
    
    try:
        policy.is_active = False
        policy.end_time = datetime.now()
        db.commit()
        flash('Policy revoked successfully!', 'success')
    except Exception as e:
        db.rollback()
        flash(f'Error revoking policy: {str(e)}', 'danger')
    
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

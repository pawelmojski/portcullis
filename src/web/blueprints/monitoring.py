"""
Monitoring Blueprint - Logs and session monitoring
"""
from flask import Blueprint, render_template, g, request, jsonify
from flask_login import login_required
from datetime import datetime, timedelta

from src.core.database import AuditLog, User, Server

monitoring_bp = Blueprint('monitoring', __name__)

@monitoring_bp.route('/')
@login_required
def index():
    """Main monitoring page"""
    return render_template('monitoring/index.html')

@monitoring_bp.route('/audit')
@login_required
def audit():
    """Audit log viewer"""
    db = g.db
    
    # Pagination
    page = request.args.get('page', 1, type=int)
    per_page = 50
    
    # Filters
    action_filter = request.args.get('action')
    user_filter = request.args.get('user')
    date_filter = request.args.get('date')
    
    query = db.query(AuditLog)
    
    if action_filter:
        query = query.filter(AuditLog.action == action_filter)
    
    if user_filter:
        query = query.filter(AuditLog.user_id == int(user_filter))
    
    if date_filter:
        date = datetime.strptime(date_filter, '%Y-%m-%d')
        query = query.filter(
            AuditLog.timestamp >= date,
            AuditLog.timestamp < date + timedelta(days=1)
        )
    
    # Get total count
    total = query.count()
    
    # Get paginated results
    logs = query.order_by(AuditLog.timestamp.desc()).offset(
        (page - 1) * per_page
    ).limit(per_page).all()
    
    # Get filter options
    actions = db.query(AuditLog.action).distinct().all()
    actions = [a[0] for a in actions]
    users = db.query(User).order_by(User.username).all()
    
    # Calculate pagination
    total_pages = (total + per_page - 1) // per_page
    
    return render_template('monitoring/audit.html',
                         logs=logs,
                         page=page,
                         total_pages=total_pages,
                         total=total,
                         actions=actions,
                         users=users,
                         action_filter=action_filter,
                         user_filter=user_filter,
                         date_filter=date_filter)

@monitoring_bp.route('/api/stats/hourly')
@login_required
def api_stats_hourly():
    """API endpoint for hourly connection statistics"""
    db = g.db
    
    # Get connections for last 24 hours, grouped by hour
    now = datetime.now()
    day_ago = now - timedelta(days=1)
    
    logs = db.query(AuditLog).filter(
        AuditLog.timestamp >= day_ago,
        AuditLog.action.in_(['ssh_access_granted', 'rdp_access_granted', 
                            'ssh_access_denied', 'rdp_access_denied'])
    ).all()
    
    # Group by hour
    hourly_data = {}
    for log in logs:
        hour = log.timestamp.replace(minute=0, second=0, microsecond=0)
        if hour not in hourly_data:
            hourly_data[hour] = {'granted': 0, 'denied': 0}
        
        if 'granted' in log.action:
            hourly_data[hour]['granted'] += 1
        else:
            hourly_data[hour]['denied'] += 1
    
    # Convert to list
    result = []
    for hour in sorted(hourly_data.keys()):
        result.append({
            'hour': hour.strftime('%H:00'),
            'granted': hourly_data[hour]['granted'],
            'denied': hourly_data[hour]['denied']
        })
    
    return jsonify(result)

@monitoring_bp.route('/api/stats/by_user')
@login_required
def api_stats_by_user():
    """API endpoint for statistics by user"""
    db = g.db
    
    # Get connections for last 7 days
    week_ago = datetime.now() - timedelta(days=7)
    
    from sqlalchemy import func
    stats = db.query(
        User.username,
        func.count(AuditLog.id).label('total')
    ).join(
        AuditLog, AuditLog.user_id == User.id
    ).filter(
        AuditLog.timestamp >= week_ago,
        AuditLog.action.in_(['ssh_access_granted', 'rdp_access_granted'])
    ).group_by(
        User.username
    ).order_by(
        func.count(AuditLog.id).desc()
    ).limit(10).all()
    
    return jsonify([{'user': s.username, 'total': s.total} for s in stats])

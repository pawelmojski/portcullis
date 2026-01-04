"""
Dashboard Blueprint - Main overview page
"""
import os
import sys
# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..')))

from flask import Blueprint, render_template, g, jsonify
from flask_login import login_required
from datetime import datetime, timedelta
from sqlalchemy import func, and_
import psutil
import subprocess

from src.core.database import SessionLocal, User, Server, AccessPolicy, AuditLog, UserSourceIP, ServerGroup, IPAllocation, Session

dashboard_bp = Blueprint('dashboard', __name__)

@dashboard_bp.route('/')
@login_required
def index():
    """Main dashboard page"""
    db = g.db
    
    # Service status
    services_status = get_services_status()
    
    # Statistics
    stats = get_statistics(db)
    
    # Recent audit log
    recent_logs = db.query(AuditLog).order_by(AuditLog.timestamp.desc()).limit(10).all()
    
    # Active sessions (placeholder - would need real-time tracking)
    active_sessions = get_active_sessions()
    
    # Servers with IP allocations
    servers = db.query(Server).order_by(Server.name).all()
    
    # Get IP allocations for each server
    server_allocations = []
    for server in servers:
        allocation = db.query(IPAllocation).filter(
            IPAllocation.server_id == server.id,
            IPAllocation.is_active == True,
            IPAllocation.expires_at == None  # Permanent allocation
        ).first()
        
        server_allocations.append({
            'server': server,
            'allocation': allocation
        })
    
    return render_template('dashboard/index.html',
                         services=services_status,
                         stats=stats,
                         recent_logs=recent_logs,
                         active_sessions=active_sessions,
                         server_allocations=server_allocations)

@dashboard_bp.route('/api/stats')
@login_required
def api_stats():
    """API endpoint for dashboard statistics (for AJAX updates)"""
    db = g.db
    stats = get_statistics(db)
    return jsonify(stats)

def get_services_status():
    """Get status of SSH and RDP proxy services"""
    services = []
    
    # Check SSH Proxy
    ssh_running = False
    try:
        result = subprocess.run(['pgrep', '-f', 'ssh_proxy.py'], 
                              capture_output=True, text=True, timeout=1)
        ssh_running = result.returncode == 0
    except:
        pass
    
    services.append({
        'name': 'SSH Proxy',
        'port': 22,
        'status': 'running' if ssh_running else 'stopped',
        'uptime': get_process_uptime('ssh_proxy.py') if ssh_running else None
    })
    
    # Check RDP Proxy
    rdp_running = False
    try:
        result = subprocess.run(['pgrep', '-f', 'pyrdp-mitm'], 
                              capture_output=True, text=True, timeout=1)
        rdp_running = result.returncode == 0
    except:
        pass
    
    services.append({
        'name': 'RDP Proxy',
        'port': 3389,
        'status': 'running' if rdp_running else 'stopped',
        'uptime': get_process_uptime('pyrdp-mitm') if rdp_running else None
    })
    
    # Check PostgreSQL
    pg_running = False
    try:
        result = subprocess.run(['systemctl', 'is-active', 'postgresql'], 
                              capture_output=True, text=True, timeout=1)
        pg_running = result.stdout.strip() == 'active'
    except:
        pass
    
    services.append({
        'name': 'PostgreSQL',
        'port': 5432,
        'status': 'running' if pg_running else 'stopped',
        'uptime': None
    })
    
    return services

def get_process_uptime(process_name):
    """Get uptime of a process"""
    try:
        result = subprocess.run(['pgrep', '-f', process_name], 
                              capture_output=True, text=True, timeout=1)
        if result.returncode == 0:
            pid = int(result.stdout.strip().split('\n')[0])
            process = psutil.Process(pid)
            create_time = datetime.fromtimestamp(process.create_time())
            uptime = datetime.now() - create_time
            
            hours = int(uptime.total_seconds() // 3600)
            minutes = int((uptime.total_seconds() % 3600) // 60)
            return f"{hours}h {minutes}m"
    except:
        pass
    return None

def get_statistics(db):
    """Get dashboard statistics"""
    now = datetime.now()
    today_start = datetime(now.year, now.month, now.day)
    
    # Total counts
    total_users = db.query(func.count(User.id)).scalar()
    total_servers = db.query(func.count(Server.id)).scalar()
    total_groups = db.query(func.count(ServerGroup.id)).scalar()
    active_policies = db.query(func.count(AccessPolicy.id)).filter(
        AccessPolicy.is_active == True,
        (AccessPolicy.end_time == None) | (AccessPolicy.end_time > now)
    ).scalar()
    
    # Today's activity
    today_connections = db.query(func.count(AuditLog.id)).filter(
        AuditLog.timestamp >= today_start,
        AuditLog.action.in_(['ssh_access_granted', 'rdp_access_granted'])
    ).scalar()
    
    today_denied = db.query(func.count(AuditLog.id)).filter(
        AuditLog.timestamp >= today_start,
        AuditLog.action.in_(['ssh_access_denied', 'rdp_access_denied'])
    ).scalar()
    
    # Recent trends (last 7 days)
    week_ago = now - timedelta(days=7)
    week_connections = db.query(func.count(AuditLog.id)).filter(
        AuditLog.timestamp >= week_ago,
        AuditLog.action.in_(['ssh_access_granted', 'rdp_access_granted'])
    ).scalar()
    
    return {
        'total_users': total_users,
        'total_servers': total_servers,
        'total_groups': total_groups,
        'active_policies': active_policies,
        'today_connections': today_connections,
        'today_denied': today_denied,
        'week_connections': week_connections,
        'success_rate': round((today_connections / (today_connections + today_denied) * 100) 
                             if (today_connections + today_denied) > 0 else 100, 1)
    }

def get_active_sessions():
    """Get currently active sessions from database"""
    db = g.db
    active = db.query(Session).filter(
        Session.is_active == True
    ).order_by(Session.started_at.desc()).limit(10).all()
    
    sessions = []
    for sess in active:
        # Build server display: ssh_username@servername for SSH, just servername for RDP
        if sess.protocol == 'ssh' and sess.ssh_username:
            server_display = f"{sess.ssh_username}@{sess.server.name if sess.server else sess.backend_ip}"
            if sess.subsystem_name:
                server_display += f" ({sess.subsystem_name})"
        else:
            server_display = sess.server.name if sess.server else sess.backend_ip
        
        sessions.append({
            'protocol': sess.protocol.upper(),
            'user': sess.user.username if sess.user else 'Unknown',
            'source_ip': sess.source_ip,
            'server': server_display,
            'backend_ip': sess.backend_ip,
            'ssh_agent': sess.ssh_agent_used if sess.protocol == 'ssh' else None,
            'started': sess.started_at
        })
    
    return sessions

"""
Mega-Search Blueprint
Unified search across sessions, policies, port forwards, users, servers, groups
"""
from flask import Blueprint, render_template, request, jsonify, send_file
from sqlalchemy import or_, and_, func, cast, String
from datetime import datetime, timedelta
import csv
import io
from src.core.database import (
    Session as DBSession, User, Server, AccessPolicy, SessionTransfer,
    UserGroup, UserGroupMember, ServerGroup, ServerGroupMember,
    SessionLocal
)

search_bp = Blueprint('search', __name__, url_prefix='/search')


def smart_detect_search_term(q):
    """Auto-detect what user is searching for"""
    if not q:
        return None, None
    
    q = q.strip()
    
    # IP address pattern
    if q.count('.') == 3:
        parts = q.split('.')
        if all(p.isdigit() and 0 <= int(p) <= 255 for p in parts):
            return 'ip', q
    
    # Policy ID pattern (e.g., "policy:42" or "#42")
    if q.startswith('policy:') or q.startswith('#'):
        policy_id = q.replace('policy:', '').replace('#', '')
        if policy_id.isdigit():
            return 'policy_id', int(policy_id)
    
    # Protocol pattern
    if q.lower() in ['ssh', 'rdp', 'vnc', 'http', 'https']:
        return 'protocol', q.lower()
    
    # Username pattern (alphanumeric with underscores/dashes)
    if q.replace('_', '').replace('-', '').isalnum():
        return 'username', q
    
    # Generic text search
    return 'text', q


def get_users_in_group(group_id, db):
    """Get all users in a group (recursive)"""
    group = db.query(UserGroup).filter_by(id=group_id).first()
    if not group:
        return []
    
    user_ids = set()
    
    # Direct members
    direct_members = db.query(UserGroupMember.user_id).filter(
        UserGroupMember.user_group_id == group_id
    ).all()
    user_ids.update([m[0] for m in direct_members])
    
    # Recursive: child groups
    child_groups = db.query(UserGroup).filter_by(parent_group_id=group_id).all()
    for child in child_groups:
        user_ids.update(get_users_in_group(child.id, db))
    
    return list(user_ids)


def get_servers_in_group(group_id, db):
    """Get all servers in a group (recursive)"""
    group = db.query(ServerGroup).filter_by(id=group_id).first()
    if not group:
        return []
    
    server_ids = set()
    
    # Direct members
    direct_members = db.query(ServerGroupMember.server_id).filter(
        ServerGroupMember.group_id == group_id
    ).all()
    server_ids.update([m[0] for m in direct_members])
    
    # Recursive: child groups
    child_groups = db.query(ServerGroup).filter_by(parent_group_id=group_id).all()
    for child in child_groups:
        server_ids.update(get_servers_in_group(child.id, db))
    
    return list(server_ids)


def build_session_query(filters, db):
    """Build dynamic query for sessions with all filters"""
    query = db.query(DBSession).outerjoin(User).outerjoin(Server).outerjoin(AccessPolicy)
    
    # Smart search detection
    if filters.get('q'):
        search_type, search_value = smart_detect_search_term(filters['q'])
        
        if search_type == 'ip':
            query = query.filter(
                or_(
                    User.username.ilike(f'%{search_value}%'),
                    Server.ip_address.ilike(f'%{search_value}%'),
                    DBSession.source_ip.ilike(f'%{search_value}%')
                )
            )
        elif search_type == 'policy_id':
            query = query.filter(DBSession.policy_id == search_value)
        elif search_type == 'protocol':
            query = query.filter(DBSession.protocol == search_value)
        elif search_type == 'username':
            query = query.filter(User.username.ilike(f'%{search_value}%'))
        elif search_type == 'text':
            query = query.filter(
                or_(
                    User.username.ilike(f'%{search_value}%'),
                    Server.name.ilike(f'%{search_value}%'),
                    Server.ip_address.ilike(f'%{search_value}%'),
                    cast(DBSession.session_id, String).ilike(f'%{search_value}%')
                )
            )
    
    # User filter
    if filters.get('user_id'):
        query = query.filter(DBSession.user_id == filters['user_id'])
    
    # User group filter
    if filters.get('user_group_id'):
        user_ids = get_users_in_group(filters['user_group_id'], db)
        if user_ids:
            query = query.filter(DBSession.user_id.in_(user_ids))
        else:
            query = query.filter(DBSession.user_id == -1)  # No results
    
    # Server filter
    if filters.get('server_id'):
        query = query.filter(DBSession.server_id == filters['server_id'])
    
    # Server group filter
    if filters.get('server_group_id'):
        server_ids = get_servers_in_group(filters['server_group_id'], db)
        if server_ids:
            query = query.filter(DBSession.server_id.in_(server_ids))
        else:
            query = query.filter(DBSession.server_id == -1)  # No results
    
    # Protocol filter
    if filters.get('protocol'):
        query = query.filter(DBSession.protocol == filters['protocol'])
    
    # Policy filter
    if filters.get('policy_id'):
        query = query.filter(DBSession.policy_id == filters['policy_id'])
    
    # Connection status filter
    if filters.get('connection_status'):
        query = query.filter(DBSession.connection_status == filters['connection_status'])
    
    # Denial reason filter
    if filters.get('denial_reason'):
        query = query.filter(DBSession.denial_reason == filters['denial_reason'])
    
    # Source IP filter
    if filters.get('source_ip'):
        query = query.filter(DBSession.source_ip.ilike(f'%{filters["source_ip"]}%'))
    
    # Time range filter
    if filters.get('time_from'):
        query = query.filter(DBSession.started_at >= filters['time_from'])
    
    if filters.get('time_to'):
        query = query.filter(DBSession.started_at <= filters['time_to'])
    
    # Port forwarding filter
    if filters.get('has_port_forwarding') == 'yes':
        query = query.filter(
            DBSession.id.in_(
                db.query(SessionTransfer.session_id).filter(
                    SessionTransfer.transfer_type.in_([
                        'port_forward_local', 'port_forward_remote', 'socks_connection'
                    ])
                )
            )
        )
    elif filters.get('has_port_forwarding') == 'no':
        query = query.filter(
            ~DBSession.id.in_(
                db.query(SessionTransfer.session_id).filter(
                    SessionTransfer.transfer_type.in_([
                        'port_forward_local', 'port_forward_remote', 'socks_connection'
                    ])
                )
            )
        )
    
    # Active/closed filter
    if filters.get('is_active') == 'yes':
        query = query.filter(DBSession.is_active == True)
    elif filters.get('is_active') == 'no':
        query = query.filter(DBSession.is_active == False)
    
    # Duration filter (in minutes)
    if filters.get('min_duration'):
        min_seconds = int(filters['min_duration']) * 60
        query = query.filter(
            func.extract('epoch', func.coalesce(DBSession.ended_at, func.now()) - DBSession.started_at) >= min_seconds
        )
    
    if filters.get('max_duration'):
        max_seconds = int(filters['max_duration']) * 60
        query = query.filter(
            func.extract('epoch', func.coalesce(DBSession.ended_at, func.now()) - DBSession.started_at) <= max_seconds
        )
    
    return query


def build_policy_query(filters, db):
    """Build dynamic query for policies"""
    query = db.query(AccessPolicy)
    
    # Smart search
    if filters.get('q'):
        search_type, search_value = smart_detect_search_term(filters['q'])
        
        if search_type == 'policy_id':
            query = query.filter(AccessPolicy.id == search_value)
        elif search_type == 'protocol':
            query = query.filter(AccessPolicy.protocol == search_value)
        elif search_type == 'text':
            query = query.join(User, AccessPolicy.user_id == User.id, isouter=True)
            query = query.join(Server, AccessPolicy.target_server_id == Server.id, isouter=True)
            query = query.filter(
                or_(
                    User.username.ilike(f'%{search_value}%'),
                    Server.name.ilike(f'%{search_value}%'),
                    AccessPolicy.reason.ilike(f'%{search_value}%')
                )
            )
    
    # User filter
    if filters.get('user_id'):
        query = query.filter(AccessPolicy.user_id == filters['user_id'])
    
    # User group filter
    if filters.get('user_group_id'):
        query = query.filter(AccessPolicy.user_group_id == filters['user_group_id'])
    
    # Server filter
    if filters.get('server_id'):
        query = query.filter(AccessPolicy.target_server_id == filters['server_id'])
    
    # Server group filter
    if filters.get('server_group_id'):
        query = query.filter(AccessPolicy.target_group_id == filters['server_group_id'])
    
    # Protocol filter
    if filters.get('protocol'):
        query = query.filter(AccessPolicy.protocol == filters['protocol'])
    
    # Policy ID filter
    if filters.get('policy_id'):
        query = query.filter(AccessPolicy.id == filters['policy_id'])
    
    # Scope type filter
    if filters.get('scope_type'):
        query = query.filter(AccessPolicy.scope_type == filters['scope_type'])
    
    # Active policies only (within time window)
    if filters.get('active_only') == 'yes':
        now = datetime.utcnow()
        query = query.filter(
            and_(
                AccessPolicy.start_time <= now,
                AccessPolicy.end_time >= now
            )
        )
    
    return query


def build_port_forwarding_query(filters, db):
    """Build dynamic query for port forwardings"""
    query = db.query(SessionTransfer).join(DBSession).join(User).join(Server)
    
    # Only port forwarding types
    query = query.filter(SessionTransfer.transfer_type.in_([
        'port_forward_local', 'port_forward_remote', 'socks_connection'
    ]))
    
    # Smart search
    if filters.get('q'):
        search_type, search_value = smart_detect_search_term(filters['q'])
        
        if search_type == 'ip':
            query = query.filter(
                or_(
                    SessionTransfer.remote_addr.ilike(f'%{search_value}%'),
                    SessionTransfer.local_addr.ilike(f'%{search_value}%')
                )
            )
        elif search_type == 'text':
            query = query.filter(
                or_(
                    User.username.ilike(f'%{search_value}%'),
                    Server.name.ilike(f'%{search_value}%'),
                    SessionTransfer.remote_addr.ilike(f'%{search_value}%')
                )
            )
    
    # User filter
    if filters.get('user_id'):
        query = query.filter(DBSession.user_id == filters['user_id'])
    
    # Server filter
    if filters.get('server_id'):
        query = query.filter(DBSession.server_id == filters['server_id'])
    
    # Protocol filter (from session)
    if filters.get('protocol'):
        query = query.filter(DBSession.protocol == filters['protocol'])
    
    # Forwarding type filter
    if filters.get('forwarding_type'):
        if filters['forwarding_type'] == 'local':
            query = query.filter(SessionTransfer.transfer_type == 'port_forward_local')
        elif filters['forwarding_type'] == 'remote':
            query = query.filter(SessionTransfer.transfer_type == 'port_forward_remote')
        elif filters['forwarding_type'] == 'dynamic':
            query = query.filter(SessionTransfer.transfer_type == 'socks_connection')
    
    # Time range
    if filters.get('time_from'):
        query = query.filter(SessionTransfer.started_at >= filters['time_from'])
    
    if filters.get('time_to'):
        query = query.filter(SessionTransfer.started_at <= filters['time_to'])
    
    # Active forwardings only
    if filters.get('is_active') == 'yes':
        query = query.filter(SessionTransfer.ended_at == None)
    elif filters.get('is_active') == 'no':
        query = query.filter(SessionTransfer.ended_at != None)
    
    return query


@search_bp.route('/', methods=['GET'])
def search():
    """Main search page"""
    db = SessionLocal()
    
    try:
        # Parse filters from query params
        filters = {}
        
        # Basic filters
        filters['q'] = request.args.get('q', '').strip()
        filters['user_id'] = request.args.get('user_id', type=int)
        filters['user_group_id'] = request.args.get('user_group_id', type=int)
        filters['server_id'] = request.args.get('server_id', type=int)
        filters['server_group_id'] = request.args.get('server_group_id', type=int)
        filters['protocol'] = request.args.get('protocol', '').strip().lower() or None
        filters['policy_id'] = request.args.get('policy_id', type=int)
        filters['connection_status'] = request.args.get('connection_status', '').strip() or None
        filters['denial_reason'] = request.args.get('denial_reason', '').strip() or None
        filters['source_ip'] = request.args.get('source_ip', '').strip() or None
        filters['has_port_forwarding'] = request.args.get('has_port_forwarding', '').strip() or None
        filters['is_active'] = request.args.get('is_active', '').strip() or None
        filters['scope_type'] = request.args.get('scope_type', '').strip() or None
        filters['active_only'] = request.args.get('active_only', '').strip() or None
        filters['forwarding_type'] = request.args.get('forwarding_type', '').strip() or None
        
        # Duration filters
        filters['min_duration'] = request.args.get('min_duration', type=int)
        filters['max_duration'] = request.args.get('max_duration', type=int)
        
        # Time range filters
        time_from_str = request.args.get('time_from', '').strip()
        time_to_str = request.args.get('time_to', '').strip()
        
        # Default to last 7 days if no time filter specified
        if not time_from_str and not time_to_str and not filters['q']:
            filters['time_from'] = datetime.utcnow() - timedelta(days=7)
        else:
            filters['time_from'] = datetime.fromisoformat(time_from_str) if time_from_str else None
            filters['time_to'] = datetime.fromisoformat(time_to_str) if time_to_str else None
        
        # Pagination
        page = request.args.get('page', 1, type=int)
        per_page = 50
        tab = request.args.get('tab', 'sessions')  # sessions, policies, port_forwards
        
        # Build queries
        sessions_query = build_session_query(filters, db)
        policies_query = build_policy_query(filters, db)
        port_forwards_query = build_port_forwarding_query(filters, db)
        
        # Get counts
        sessions_count = sessions_query.count()
        policies_count = policies_query.count()
        port_forwards_count = port_forwards_query.count()
        
        # Get paginated results for active tab
        if tab == 'sessions':
            from sqlalchemy.orm import joinedload
            results = sessions_query.options(joinedload(DBSession.transfers)).order_by(DBSession.started_at.desc()).offset((page - 1) * per_page).limit(per_page).all()
            total_count = sessions_count
        elif tab == 'policies':
            results = policies_query.order_by(AccessPolicy.start_time.desc()).offset((page - 1) * per_page).limit(per_page).all()
            total_count = policies_count
        elif tab == 'port_forwards':
            results = port_forwards_query.order_by(SessionTransfer.started_at.desc()).offset((page - 1) * per_page).limit(per_page).all()
            total_count = port_forwards_count
        else:
            results = []
            total_count = 0
        
        # Calculate pagination
        total_pages = (total_count + per_page - 1) // per_page
        
        # Get dropdown data
        all_users = db.query(User).filter_by(is_active=True).order_by(User.username).all()
        all_user_groups = db.query(UserGroup).order_by(UserGroup.name).all()
        all_servers = db.query(Server).order_by(Server.name).all()
        all_server_groups = db.query(ServerGroup).order_by(ServerGroup.name).all()
        all_policies = db.query(AccessPolicy).order_by(AccessPolicy.id.desc()).limit(100).all()
        
        # Get unique values for dropdowns
        protocols = db.query(DBSession.protocol).distinct().all()
        protocols = [p[0] for p in protocols if p[0]]
        
        connection_statuses = db.query(DBSession.connection_status).distinct().all()
        connection_statuses = [s[0] for s in connection_statuses if s[0]]
        
        denial_reasons = db.query(DBSession.denial_reason).distinct().all()
        denial_reasons = [r[0] for r in denial_reasons if r[0]]
        
        return render_template(
            'search/index.html',
            results=results,
            tab=tab,
            page=page,
            total_pages=total_pages,
            total_count=total_count,
            sessions_count=sessions_count,
            policies_count=policies_count,
            port_forwards_count=port_forwards_count,
            filters=filters,
            all_users=all_users,
            all_user_groups=all_user_groups,
            all_servers=all_servers,
            all_server_groups=all_server_groups,
            all_policies=all_policies,
            protocols=protocols,
            connection_statuses=connection_statuses,
            denial_reasons=denial_reasons,
            per_page=per_page
        )
    
    finally:
        db.close()


@search_bp.route('/export', methods=['GET'])
def export_csv():
    """Export search results to CSV"""
    db = SessionLocal()
    
    try:
        # Parse same filters as search
        filters = {}
        filters['q'] = request.args.get('q', '').strip()
        filters['user_id'] = request.args.get('user_id', type=int)
        filters['user_group_id'] = request.args.get('user_group_id', type=int)
        filters['server_id'] = request.args.get('server_id', type=int)
        filters['server_group_id'] = request.args.get('server_group_id', type=int)
        filters['protocol'] = request.args.get('protocol', '').strip().lower() or None
        filters['policy_id'] = request.args.get('policy_id', type=int)
        filters['connection_status'] = request.args.get('connection_status', '').strip() or None
        filters['denial_reason'] = request.args.get('denial_reason', '').strip() or None
        filters['source_ip'] = request.args.get('source_ip', '').strip() or None
        filters['has_port_forwarding'] = request.args.get('has_port_forwarding', '').strip() or None
        filters['is_active'] = request.args.get('is_active', '').strip() or None
        
        time_from_str = request.args.get('time_from', '').strip()
        time_to_str = request.args.get('time_to', '').strip()
        filters['time_from'] = datetime.fromisoformat(time_from_str) if time_from_str else None
        filters['time_to'] = datetime.fromisoformat(time_to_str) if time_to_str else None
        
        tab = request.args.get('tab', 'sessions')
        
        # Build query
        if tab == 'sessions':
            query = build_session_query(filters, db)
            results = query.order_by(DBSession.started_at.desc()).limit(10000).all()
            
            # Create CSV
            output = io.StringIO()
            writer = csv.writer(output)
            writer.writerow([
                'Session ID', 'User', 'Server', 'Protocol', 'Policy ID',
                'Connection Status', 'Denial Reason', 'Source IP',
                'Protocol Version', 'Started At', 'Ended At', 'Duration (min)'
            ])
            
            for session in results:
                duration = None
                if session.ended_at:
                    duration = int((session.ended_at - session.started_at).total_seconds() / 60)
                elif session.started_at:
                    duration = int((datetime.utcnow() - session.started_at).total_seconds() / 60)
                
                writer.writerow([
                    session.session_id,
                    session.user.username if session.user else '',
                    f"{session.server.name} ({session.server.ip_address})" if session.server else '',
                    session.protocol or '',
                    session.policy_id or '',
                    session.connection_status or '',
                    session.denial_reason or '',
                    session.source_ip or '',
                    session.protocol_version or '',
                    session.started_at.isoformat() if session.started_at else '',
                    session.ended_at.isoformat() if session.ended_at else '',
                    duration or ''
                ])
            
            filename = f'sessions_export_{datetime.utcnow().strftime("%Y%m%d_%H%M%S")}.csv'
        
        elif tab == 'policies':
            query = build_policy_query(filters, db)
            results = query.order_by(AccessPolicy.start_time.desc()).limit(10000).all()
            
            output = io.StringIO()
            writer = csv.writer(output)
            writer.writerow([
                'Policy ID', 'Scope Type', 'User', 'User Group', 'Server', 'Server Group',
                'Protocol', 'Start Time', 'End Time', 'Description'
            ])
            
            for policy in results:
                writer.writerow([
                    policy.id,
                    policy.scope_type,
                    policy.user.username if policy.user else '',
                    policy.user_group.name if policy.user_group else '',
                    f"{policy.target_server.name}" if policy.target_server else '',
                    policy.target_group.name if policy.target_group else '',
                    policy.protocol or 'any',
                    policy.start_time.isoformat() if policy.start_time else '',
                    policy.end_time.isoformat() if policy.end_time else '',
                    policy.reason or ''
                ])
            
            filename = f'policies_export_{datetime.utcnow().strftime("%Y%m%d_%H%M%S")}.csv'
        
        elif tab == 'port_forwards':
            query = build_port_forwarding_query(filters, db)
            results = query.order_by(SessionTransfer.started_at.desc()).limit(10000).all()
            
            output = io.StringIO()
            writer = csv.writer(output)
            writer.writerow([
                'Transfer ID', 'Session ID', 'User', 'Server', 'Type',
                'Local Addr', 'Local Port', 'Remote Addr', 'Remote Port',
                'Bytes Sent', 'Bytes Received', 'Started At', 'Ended At'
            ])
            
            for fwd in results:
                writer.writerow([
                    fwd.id,
                    fwd.session.session_id if fwd.session else '',
                    fwd.session.user.username if fwd.session and fwd.session.user else '',
                    fwd.session.server.name if fwd.session and fwd.session.server else '',
                    fwd.transfer_type,
                    fwd.local_addr or '',
                    fwd.local_port or '',
                    fwd.remote_addr or '',
                    fwd.remote_port or '',
                    fwd.bytes_sent or 0,
                    fwd.bytes_received or 0,
                    fwd.started_at.isoformat() if fwd.started_at else '',
                    fwd.ended_at.isoformat() if fwd.ended_at else ''
                ])
            
            filename = f'port_forwards_export_{datetime.utcnow().strftime("%Y%m%d_%H%M%S")}.csv'
        
        else:
            return "Invalid tab", 400
        
        # Send file
        output.seek(0)
        return send_file(
            io.BytesIO(output.getvalue().encode('utf-8')),
            mimetype='text/csv',
            as_attachment=True,
            download_name=filename
        )
    
    finally:
        db.close()

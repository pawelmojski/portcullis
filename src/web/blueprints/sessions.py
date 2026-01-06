"""
Sessions Blueprint - Session History and Log Viewer
"""

from flask import Blueprint, render_template, request, jsonify, send_file, abort
from src.core.database import SessionLocal, Session, User, Server
from datetime import datetime, timedelta
import json
import os
from pathlib import Path
from functools import lru_cache
import time

sessions_bp = Blueprint('sessions', __name__, url_prefix='/sessions')

# Recording paths
SSH_RECORDING_DIR = '/var/log/jumphost/ssh_recordings'
RDP_RECORDING_DIR = '/var/log/jumphost/rdp_recordings/replays'

# Cache for parsed recordings (file_path -> (mtime, parsed_data))
_recording_cache = {}


def get_cached_recording(file_path):
    """
    Get parsed recording from cache or parse if needed.
    Cache is invalidated when file modification time changes.
    """
    if not os.path.exists(file_path):
        return None
    
    current_mtime = os.path.getmtime(file_path)
    
    # Check cache
    if file_path in _recording_cache:
        cached_mtime, cached_data = _recording_cache[file_path]
        if cached_mtime == current_mtime:
            return cached_data
    
    # Parse and cache
    parsed_data = parse_ssh_recording_internal(file_path)
    _recording_cache[file_path] = (current_mtime, parsed_data)
    
    # Limit cache size to 50 entries
    if len(_recording_cache) > 50:
        # Remove oldest entries
        oldest_keys = sorted(_recording_cache.keys(), 
                           key=lambda k: _recording_cache[k][0])[:10]
        for key in oldest_keys:
            del _recording_cache[key]
    
    return parsed_data


def get_full_recording_path(session):
    """
    Get full path to recording file based on protocol and filename.
    Returns None if no recording path set.
    """
    if not session.recording_path:
        # Try to find file by session_id if path not set
        if session.protocol == 'ssh':
            # SSH format: timestamp_username_server_source_{session_id}.log
            import glob
            pattern = os.path.join(SSH_RECORDING_DIR, f'*{session.session_id}.log')
            matches = glob.glob(pattern)
            if matches:
                return matches[0]
        elif session.protocol == 'rdp':
            # RDP format: rdp_replay_*_{session_id}.pyrdp
            import glob
            pattern = os.path.join(RDP_RECORDING_DIR, f'*{session.session_id}.pyrdp')
            matches = glob.glob(pattern)
            if matches:
                return matches[0]
        return None
    
    # If already absolute path, return as-is
    if os.path.isabs(session.recording_path):
        return session.recording_path
    
    # Otherwise construct full path based on protocol
    if session.protocol == 'ssh':
        return os.path.join(SSH_RECORDING_DIR, session.recording_path)
    elif session.protocol == 'rdp':
        return os.path.join(RDP_RECORDING_DIR, session.recording_path)
    
    return session.recording_path


def recording_exists(session):
    """
    Check if recording file actually exists on filesystem.
    """
    full_path = get_full_recording_path(session)
    if not full_path:
        return False
    return os.path.exists(full_path)


def parse_ssh_recording(file_path):
    """
    Parse SSH recording with caching support.
    """
    return get_cached_recording(file_path)


def parse_ssh_recording_internal(file_path):
    """
    Internal parser - Parse SSH recording JSON/log file and return human-readable log entries.
    Returns dict with session info and list of log entries.
    """
    if not os.path.exists(file_path):
        return None
    
    def ansi_to_html(text):
        """Convert ANSI escape sequences to HTML with colors"""
        import re
        
        # First, remove non-SGR escape sequences (they don't affect display)
        # Remove CSI sequences (except SGR): ESC [ ... (not ending in 'm')
        text = re.sub(r'\x1b\[[0-9;?]*[A-Zac-ln-z]', '', text)
        # Remove OSC sequences: ESC ] ... BEL or ESC ] ... ESC \
        text = re.sub(r'\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)', '', text)
        # Remove other escape sequences
        text = re.sub(r'\x1b[()][AB012]', '', text)  # Character set selection
        text = re.sub(r'\x1b[=>]', '', text)  # Keypad mode
        
        # ANSI color map (SGR parameters)
        colors = {
            '30': '#000000', '31': '#cd0000', '32': '#00cd00', '33': '#cdcd00',
            '34': '#0000ee', '35': '#cd00cd', '36': '#00cdcd', '37': '#e5e5e5',
            '90': '#7f7f7f', '91': '#ff0000', '92': '#00ff00', '93': '#ffff00',
            '94': '#5c5cff', '95': '#ff00ff', '96': '#00ffff', '97': '#ffffff',
        }
        
        bg_colors = {
            '40': '#000000', '41': '#cd0000', '42': '#00cd00', '43': '#cdcd00',
            '44': '#0000ee', '45': '#cd00cd', '46': '#00cdcd', '47': '#e5e5e5',
            '100': '#7f7f7f', '101': '#ff0000', '102': '#00ff00', '103': '#ffff00',
            '104': '#5c5cff', '105': '#ff00ff', '106': '#00ffff', '107': '#ffffff',
        }
        
        # Current style state
        current_fg = None
        current_bg = None
        bold = False
        
        result = []
        open_span = False
        
        # Split by ESC sequences
        parts = re.split(r'(\x1b\[[0-9;]*m)', text)
        
        for part in parts:
            if part.startswith('\x1b[') and part.endswith('m'):
                # Parse SGR sequence
                codes = part[2:-1].split(';')
                
                for code in codes:
                    if code == '' or code == '0':
                        # Reset
                        if open_span:
                            result.append('</span>')
                            open_span = False
                        current_fg = None
                        current_bg = None
                        bold = False
                    elif code == '1':
                        bold = True
                    elif code == '22':
                        bold = False
                    elif code in colors:
                        current_fg = colors[code]
                    elif code in bg_colors:
                        current_bg = bg_colors[code]
                
                # Close previous span if any
                if open_span:
                    result.append('</span>')
                    open_span = False
                
                # Open new span with current styles
                if current_fg or current_bg or bold:
                    styles = []
                    if current_fg:
                        styles.append(f'color: {current_fg}')
                    if current_bg:
                        styles.append(f'background-color: {current_bg}')
                    if bold:
                        styles.append('font-weight: bold')
                    result.append(f'<span style="{"; ".join(styles)}">')
                    open_span = True
            else:
                # Regular text - escape HTML but preserve structure
                import html
                result.append(html.escape(part))
        
        # Close any open span
        if open_span:
            result.append('</span>')
        
        return ''.join(result)
    
    try:
        with open(file_path, 'r') as f:
            data = json.load(f)
        
        events = data.get('events', [])
        start_time_str = data.get('start_time') or data.get('session_start', '')
        end_time_str = data.get('end_time', '')
        
        # Parse start time
        if start_time_str:
            session_start = datetime.fromisoformat(start_time_str.replace('Z', '+00:00'))
        else:
            session_start = datetime.now()
        
        log_entries = []
        
        for event in events:
            # Parse event timestamp
            event_ts_str = event.get('timestamp', '')
            if event_ts_str:
                event_ts = datetime.fromisoformat(event_ts_str.replace('Z', '+00:00'))
                # Calculate elapsed seconds from session start
                elapsed_seconds = (event_ts - session_start).total_seconds()
            else:
                elapsed_seconds = 0
            
            event_type = event.get('type', 'unknown')
            content = event.get('data', '')
            
            # Skip client_to_server events that don't contain newline/return
            # (these are individual keystrokes that will be echoed by server anyway)
            if event_type == 'client_to_server':
                if '\n' not in content and '\r' not in content and len(content) < 2:
                    continue  # Skip single character keystrokes
            
            # Format elapsed time
            if elapsed_seconds < 60:
                elapsed_str = f"{int(elapsed_seconds)}s"
            elif elapsed_seconds < 3600:
                minutes = int(elapsed_seconds // 60)
                seconds = int(elapsed_seconds % 60)
                elapsed_str = f"{minutes}m {seconds}s"
            else:
                hours = int(elapsed_seconds // 3600)
                minutes = int((elapsed_seconds % 3600) // 60)
                elapsed_str = f"{hours}h {minutes}m"
            
            # Clean up content - remove excessive whitespace and control chars for display
            display_content = content
            if event_type in ['server_to_client', 'client_to_server']:
                # Truncate before conversion (to avoid huge HTML)
                original_length = len(content)
                truncated = False
                if original_length > 2000:
                    content = content[:2000]
                    truncated = True
                
                # Convert ANSI escape sequences to HTML
                display_content = ansi_to_html(content)
                
                if truncated:
                    display_content += '... (truncated)'
            
            entry = {
                'timestamp': event_ts_str,
                'elapsed': elapsed_str,
                'elapsed_seconds': elapsed_seconds,
                'type': event_type,
                'content': display_content,
                'content_length': len(content),
                'raw': event
            }
            
            log_entries.append(entry)
        
        # Group consecutive events of the same type within 100ms
        grouped_entries = []
        for entry in log_entries:
            if entry['type'] in ['session_start', 'session_end']:
                grouped_entries.append(entry)
                continue
            
            # Try to merge with previous entry if same type and within 100ms
            if (grouped_entries and 
                grouped_entries[-1]['type'] == entry['type'] and
                entry['elapsed_seconds'] - grouped_entries[-1]['elapsed_seconds'] < 0.1):
                # Merge content
                grouped_entries[-1]['content'] += entry['content']
                grouped_entries[-1]['content_length'] += entry['content_length']
            else:
                grouped_entries.append(entry)
        
        # Calculate total duration
        if end_time_str:
            end_time = datetime.fromisoformat(end_time_str.replace('Z', '+00:00'))
            duration_seconds = (end_time - session_start).total_seconds()
        else:
            duration_seconds = data.get('duration_seconds', 0)
        
        return {
            'session_start': start_time_str,
            'session_end': end_time_str,
            'total_duration': f"{int(duration_seconds)}s",
            'total_events': len(events),
            'log_entries': grouped_entries,
            'username': data.get('username', 'unknown'),
            'server_ip': data.get('server_ip', 'unknown')
        }
    except Exception as e:
        return {'error': str(e)}


def get_rdp_recording_info(file_path):
    """
    Get RDP recording file information and parse JSON if available.
    """
    if not os.path.exists(file_path):
        return None
    
    file_stat = os.stat(file_path)
    
    info = {
        'file_path': file_path,
        'file_name': os.path.basename(file_path),
        'file_size': file_stat.st_size,
        'file_size_mb': round(file_stat.st_size / (1024 * 1024), 2),
        'modified_time': datetime.fromtimestamp(file_stat.st_mtime).isoformat(),
        'has_json': False,
        'json_data': None
    }
    
    # Check if JSON version exists in cache
    # Note: pyrdp-convert appends source filename to output, so we use cache directory only
    json_cache_dir = '/var/log/jumphost/rdp_recordings/json_cache'
    base_name = os.path.basename(file_path)
    
    # Find JSON file - pyrdp-convert creates: {output_path}-{source_filename}.json
    json_pattern = os.path.join(json_cache_dir, f"*{base_name.replace('.pyrdp', '')}.json")
    import glob
    existing_json = glob.glob(json_pattern)
    json_file = existing_json[0] if existing_json else None
    
    # Convert to JSON if not cached or outdated
    if not json_file or not os.path.exists(json_file) or os.path.getmtime(json_file) < file_stat.st_mtime:
        try:
            # Create cache directory
            os.makedirs(json_cache_dir, exist_ok=True)
            
            # Convert .pyrdp to JSON - specify cache directory, pyrdp-convert will append filename
            import subprocess
            cache_output = os.path.join(json_cache_dir, 'cached')
            result = subprocess.run(
                ['pyrdp-convert', '-f', 'json', '-o', cache_output, file_path],
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode != 0:
                return info  # Return basic info if conversion fails
            
            # Find the created JSON file
            existing_json = glob.glob(json_pattern)
            json_file = existing_json[0] if existing_json else None
        except Exception as e:
            return info
    
    # Parse JSON if it exists
    if json_file and os.path.exists(json_file):
        try:
            with open(json_file, 'r') as f:
                json_data = json.load(f)
            
            info['has_json'] = True
            info['json_data'] = json_data
            
            # Extract metadata
            if 'info' in json_data:
                metadata = json_data['info']
                info['metadata'] = {
                    'host': metadata.get('host', 'Unknown'),
                    'username': metadata.get('username', ''),
                    'domain': metadata.get('domain', ''),
                    'width': metadata.get('width', 0),
                    'height': metadata.get('height', 0),
                    'date': datetime.fromtimestamp(metadata.get('date', 0) / 1000).isoformat() if metadata.get('date') else None
                }
            
            # Parse events
            if 'events' in json_data:
                events = json_data['events']
                info['total_events'] = len(events)
                
                # Count event types
                key_events = [e for e in events if e.get('type') == 'key']
                mouse_events = [e for e in events if e.get('type') == 'mouse']
                
                info['event_summary'] = {
                    'keyboard': len(key_events),
                    'mouse': len(mouse_events)
                }
                
                # Calculate duration (from first to last event)
                if events:
                    first_ts = events[0].get('timestamp', 0)
                    last_ts = events[-1].get('timestamp', 0)
                    duration_ms = last_ts - first_ts
                    info['duration_seconds'] = duration_ms / 1000
                    info['duration_formatted'] = format_duration(duration_ms / 1000)
        except Exception as e:
            pass
    
    return info


def format_duration(seconds):
    """Format duration in seconds to human-readable string"""
    if seconds < 60:
        return f"{int(seconds)}s"
    elif seconds < 3600:
        minutes = int(seconds // 60)
        secs = int(seconds % 60)
        return f"{minutes}m {secs}s"
    else:
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        return f"{hours}h {minutes}m"



@sessions_bp.route('/')
def index():
    """List all sessions with filtering and pagination"""
    db = SessionLocal()
    try:
        # Get filter parameters
        protocol_filter = request.args.get('protocol', '')
        user_filter = request.args.get('user', '')
        server_filter = request.args.get('server', '')
        status_filter = request.args.get('status', 'all')  # all, active, closed
        page = int(request.args.get('page', 1))
        per_page = 20
        
        # Build query
        query = db.query(Session).join(User).join(Server)
        
        if protocol_filter:
            query = query.filter(Session.protocol == protocol_filter)
        
        if user_filter:
            query = query.filter(User.username.ilike(f'%{user_filter}%'))
        
        if server_filter:
            query = query.filter(Server.name.ilike(f'%{server_filter}%'))
        
        if status_filter == 'active':
            query = query.filter(Session.is_active == True)
        elif status_filter == 'closed':
            query = query.filter(Session.is_active == False)
        
        # Order by most recent first
        query = query.order_by(Session.started_at.desc())
        
        # Pagination
        total = query.count()
        sessions = query.offset((page - 1) * per_page).limit(per_page).all()
        
        # Get unique values for filters
        all_protocols = db.query(Session.protocol).distinct().all()
        protocols = [p[0] for p in all_protocols]
        
        return render_template('sessions/index.html',
                             sessions=sessions,
                             protocols=protocols,
                             current_protocol=protocol_filter,
                             current_user=user_filter,
                             current_server=server_filter,
                             current_status=status_filter,
                             page=page,
                             per_page=per_page,
                             total=total,
                             total_pages=(total + per_page - 1) // per_page,
                             recording_exists=recording_exists)
    finally:
        db.close()


@sessions_bp.route('/<session_id>')
def view(session_id):
    """View session details and log"""
    db = SessionLocal()
    try:
        from src.core.database import SessionTransfer
        
        session = db.query(Session).filter(Session.session_id == session_id).first()
        
        if not session:
            abort(404)
        
        # Get transfer details (SCP/SFTP/port forwarding/SOCKS)
        transfers = db.query(SessionTransfer).filter(
            SessionTransfer.session_id == session.id
        ).order_by(SessionTransfer.started_at).all()
        
        # Parse recording based on protocol
        recording_data = None
        recording_info = None
        file_exists = recording_exists(session)
        
        # For active SSH sessions, try to parse even if file_exists is False
        # (file might be in-progress)
        if session.protocol == 'ssh':
            if file_exists or session.is_active:
                full_path = get_full_recording_path(session)
                if full_path:
                    recording_data = parse_ssh_recording(full_path)
        elif session.protocol == 'rdp' and file_exists:
            full_path = get_full_recording_path(session)
            recording_info = get_rdp_recording_info(full_path)
        
        return render_template('sessions/view.html',
                             session=session,
                             transfers=transfers,
                             recording_data=recording_data,
                             recording_info=recording_info,
                             file_exists=file_exists,
                             is_active=session.is_active)
    finally:
        db.close()


@sessions_bp.route('/<session_id>/live')
def live_events(session_id):
    """
    Get live session events for active SSH sessions.
    Returns events after a given timestamp (for polling).
    """
    db = SessionLocal()
    try:
        session = db.query(Session).filter(Session.session_id == session_id).first()
        
        if not session:
            return jsonify({'error': 'Session not found'}), 404
        
        if not session.is_active:
            return jsonify({'error': 'Session is not active', 'is_active': False}), 200
        
        if session.protocol != 'ssh':
            return jsonify({'error': 'Live view only supported for SSH'}), 400
        
        # Get the 'after' parameter (timestamp to get events after)
        after_seconds = float(request.args.get('after', 0))
        
        # Get recording file
        full_path = get_full_recording_path(session)
        if not full_path or not os.path.exists(full_path):
            return jsonify({'error': 'Recording file not found'}), 404
        
        # Parse recording and filter events after timestamp
        recording_data = parse_ssh_recording(full_path)
        if not recording_data or 'error' in recording_data:
            return jsonify({'error': 'Failed to parse recording'}), 500
        
        # Filter events that are newer than 'after' timestamp
        new_events = [
            entry for entry in recording_data['log_entries']
            if entry['elapsed_seconds'] > after_seconds
        ]
        
        return jsonify({
            'is_active': session.is_active,
            'events': new_events,
            'total_events': recording_data['total_events'],
            'session_duration': recording_data['total_duration']
        })
    finally:
        db.close()


@sessions_bp.route('/<session_id>/download')
def download(session_id):
    """Download session recording file"""
    db = SessionLocal()
    try:
        session = db.query(Session).filter(Session.session_id == session_id).first()
        
        if not session:
            abort(404)
        
        if not recording_exists(session):
            abort(404)
        
        full_path = get_full_recording_path(session)
        
        # Determine filename and mimetype
        if session.protocol == 'ssh':
            filename = f"ssh_session_{session_id}.json"
            mimetype = 'application/json'
        else:
            filename = os.path.basename(full_path)
            mimetype = 'application/octet-stream'
        
        return send_file(full_path,
                        mimetype=mimetype,
                        as_attachment=True,
                        download_name=filename)
    finally:
        db.close()


@sessions_bp.route('/<session_id>/rdp-events')
def rdp_events(session_id):
    """Get RDP session events as JSON (converted from .pyrdp)"""
    db = SessionLocal()
    try:
        session = db.query(Session).filter(Session.session_id == session_id).first()
        
        if not session or session.protocol != 'rdp':
            abort(404)
        
        if not recording_exists(session):
            return jsonify({'error': 'Recording not found'}), 404
        
        full_path = get_full_recording_path(session)
        rdp_info = get_rdp_recording_info(full_path)
        
        if not rdp_info or not rdp_info.get('has_json'):
            return jsonify({'error': 'Failed to convert recording to JSON'}), 500
        
        return jsonify(rdp_info['json_data'])
    finally:
        db.close()


@sessions_bp.route('/<session_id>/log')
def log_json(session_id):
    """Get session log as JSON (for AJAX requests)"""
    db = SessionLocal()
    try:
        session = db.query(Session).filter(Session.session_id == session_id).first()
        
        if not session:
            return jsonify({'error': 'Session not found'}), 404
        
        if not recording_exists(session):
            return jsonify({'error': 'Recording file not found'}), 404
        
        full_path = get_full_recording_path(session)
        
        if session.protocol == 'ssh':
            recording_data = parse_ssh_recording(full_path)
            return jsonify(recording_data)
        elif session.protocol == 'rdp':
            recording_info = get_rdp_recording_info(full_path)
            return jsonify(recording_info)
        else:
            return jsonify({'error': 'No recording available'}), 404
    finally:
        db.close()


@sessions_bp.route('/<session_id>/convert', methods=['POST'])
def convert_to_mp4(session_id):
    """Queue RDP session for MP4 conversion"""
    from src.core.database import MP4ConversionQueue
    
    db = SessionLocal()
    try:
        # Verify session exists
        session = db.query(Session).filter(Session.session_id == session_id).first()
        if not session:
            return jsonify({'error': 'Session not found'}), 404
        
        if session.protocol != 'rdp':
            return jsonify({'error': 'Only RDP sessions can be converted to MP4'}), 400
        
        # Check if already in queue or completed
        existing = db.query(MP4ConversionQueue).filter(
            MP4ConversionQueue.session_id == session_id
        ).first()
        
        if existing:
            if existing.status == 'completed':
                return jsonify({'message': 'Already converted', 'status': existing.status})
            elif existing.status in ['pending', 'converting']:
                return jsonify({'message': 'Already in queue', 'status': existing.status})
            elif existing.status == 'failed':
                # Retry failed conversion
                existing.status = 'pending'
                existing.error_msg = None
                existing.progress = 0
                existing.total = 0
                existing.created_at = datetime.utcnow()
                db.commit()
                return jsonify({'message': 'Queued for retry', 'status': 'pending'})
        
        # Check queue size
        pending_count = db.query(MP4ConversionQueue).filter(
            MP4ConversionQueue.status == 'pending'
        ).count()
        
        if pending_count >= 10:
            return jsonify({'error': 'Conversion queue is full (max 10 pending)'}), 429
        
        # Add to queue
        new_job = MP4ConversionQueue(
            session_id=session_id,
            status='pending',
            priority=0
        )
        db.add(new_job)
        db.commit()
        
        return jsonify({
            'message': 'Queued for conversion',
            'status': 'pending',
            'position': pending_count + 1
        })
        
    finally:
        db.close()


@sessions_bp.route('/<session_id>/convert/priority', methods=['POST'])
def prioritize_conversion(session_id):
    """Move conversion to front of queue (admin only - TODO: add permission check)"""
    from src.core.database import MP4ConversionQueue
    
    db = SessionLocal()
    try:
        job = db.query(MP4ConversionQueue).filter(
            MP4ConversionQueue.session_id == session_id
        ).first()
        
        if not job:
            return jsonify({'error': 'Conversion job not found'}), 404
        
        if job.status != 'pending':
            return jsonify({'error': f'Cannot prioritize job with status: {job.status}'}), 400
        
        # Set highest priority (max current + 1)
        max_priority = db.query(MP4ConversionQueue.priority).filter(
            MP4ConversionQueue.status == 'pending'
        ).order_by(MP4ConversionQueue.priority.desc()).first()
        
        job.priority = (max_priority[0] if max_priority else 0) + 1
        db.commit()
        
        return jsonify({
            'message': 'Moved to front of queue',
            'priority': job.priority
        })
        
    finally:
        db.close()


@sessions_bp.route('/<session_id>/convert-status')
def conversion_status(session_id):
    """Get MP4 conversion status"""
    from src.core.database import MP4ConversionQueue
    
    db = SessionLocal()
    try:
        job = db.query(MP4ConversionQueue).filter(
            MP4ConversionQueue.session_id == session_id
        ).first()
        
        if not job:
            return jsonify({'status': 'not_queued'})
        
        # Calculate queue position if pending
        position = None
        if job.status == 'pending':
            position = db.query(MP4ConversionQueue).filter(
                MP4ConversionQueue.status == 'pending',
                (MP4ConversionQueue.priority > job.priority) | 
                ((MP4ConversionQueue.priority == job.priority) & 
                 (MP4ConversionQueue.created_at < job.created_at))
            ).count() + 1
        
        # Calculate progress percentage
        percent = 0
        if job.total and job.total > 0:
            percent = int((job.progress / job.total) * 100)
        
        return jsonify({
            'status': job.status,
            'progress': job.progress,
            'total': job.total,
            'percent': percent,
            'eta_seconds': job.eta_seconds,
            'position': position,
            'error_msg': job.error_msg,
            'mp4_available': job.status == 'completed' and job.mp4_path and os.path.exists(job.mp4_path)
        })
        
    finally:
        db.close()


@sessions_bp.route('/<session_id>/mp4/stream')
def stream_mp4(session_id):
    """Stream MP4 file with range support (for HTML5 video player)"""
    from src.core.database import MP4ConversionQueue
    
    db = SessionLocal()
    try:
        job = db.query(MP4ConversionQueue).filter(
            MP4ConversionQueue.session_id == session_id,
            MP4ConversionQueue.status == 'completed'
        ).first()
        
        if not job or not job.mp4_path or not os.path.exists(job.mp4_path):
            return jsonify({'error': 'MP4 file not available'}), 404
        
        # Support range requests for video seeking
        return send_file(
            job.mp4_path,
            mimetype='video/mp4',
            as_attachment=False,
            conditional=True
        )
        
    finally:
        db.close()


@sessions_bp.route('/<session_id>/mp4', methods=['DELETE'])
def delete_mp4(session_id):
    """Delete MP4 file and reset conversion status"""
    from src.core.database import MP4ConversionQueue
    
    db = SessionLocal()
    try:
        job = db.query(MP4ConversionQueue).filter(
            MP4ConversionQueue.session_id == session_id
        ).first()
        
        if not job:
            return jsonify({'error': 'Conversion record not found'}), 404
        
        # Delete MP4 file if exists
        if job.mp4_path and os.path.exists(job.mp4_path):
            os.remove(job.mp4_path)
        
        # Remove from database
        db.delete(job)
        db.commit()
        
        return jsonify({'message': 'MP4 deleted successfully'})
        
    finally:
        db.close()

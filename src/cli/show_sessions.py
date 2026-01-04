#!/opt/jumphost/venv/bin/python3
"""
Show active proxy sessions - equivalent to 'w' but for jumphost sessions
"""
import sys
from pathlib import Path
from datetime import datetime, timedelta

# Add project root to path
sys.path.insert(0, '/opt/jumphost')

from src.core.database import SessionLocal, Session

def format_duration(seconds):
    """Format duration in human readable format"""
    if seconds < 60:
        return f"{seconds}s"
    elif seconds < 3600:
        return f"{seconds // 60}m"
    elif seconds < 86400:
        hours = seconds // 3600
        mins = (seconds % 3600) // 60
        return f"{hours}h{mins:02d}m"
    else:
        days = seconds // 86400
        hours = (seconds % 86400) // 3600
        return f"{days}d{hours}h"

def show_sessions():
    """Display active proxy sessions"""
    db = SessionLocal()
    try:
        # Get active sessions
        sessions = db.query(Session).filter(
            Session.is_active == True
        ).order_by(Session.started_at.desc()).all()
        
        if not sessions:
            print("No active proxy sessions")
            return
        
        # Print header
        now = datetime.utcnow()
        uptime_str = "jumphost sessions"
        print(f" {now.strftime('%H:%M:%S')} {uptime_str}")
        print(f"{'USER':<12} {'TTY':<8} {'PROTO':<6} {'FROM':<16} {'LOGIN@':<8} {'IDLE':<8} {'WHAT'}")
        
        # Print sessions
        for sess in sessions:
            duration = int((now - sess.started_at).total_seconds())
            idle_str = format_duration(duration)
            login_time = sess.started_at.strftime('%H:%M')
            
            # Build "WHAT" - what user is doing
            if sess.protocol == 'ssh':
                what = f"{sess.ssh_username}@{sess.server.name if sess.server else sess.backend_ip}"
                if sess.subsystem_name:
                    what += f":{sess.subsystem_name}"
            else:
                what = f"RDP to {sess.server.name if sess.server else sess.backend_ip}"
            
            tty = f"{sess.protocol}{sess.id % 100}"
            user = sess.user.username if sess.user else "unknown"
            
            print(f"{user:<12} {tty:<8} {sess.protocol.upper():<6} {sess.source_ip:<16} {login_time:<8} {idle_str:<8} {what}")
        
    finally:
        db.close()

if __name__ == "__main__":
    show_sessions()

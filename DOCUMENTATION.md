# Jump Host - SSH/RDP Proxy with Access Control

## Project Overview

Self-made SSH/RDP jump host with temporal access control, source IP mapping, session recording, real-time monitoring, and system logging integration.

## Architecture (Current State - v1.1)

```
┌─────────────────────────────────────────────────────────────────┐
│                         JUMP HOST                                │
│                      (10.0.160.5)                                │
│                                                                   │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  Web Management Interface (5000)                ⭐ NEW   │   │
│  │                                                            │   │
│  │  Flask Web GUI (Bootstrap 5)                              │   │
│  │  - Dashboard: Service status, statistics, charts          │   │
│  │  - Active Sessions: Real-time monitoring widget 🎯 NEW   │   │
│  │  - User Management: CRUD + multiple source IPs            │   │
│  │  - Server Management: CRUD + IP allocation                │   │
│  │  - Group Management: Create groups, assign servers        │   │
│  │  - Policy Wizard: Grant access with flexible scopes       │   │
│  │  - Monitoring: Audit logs with filters, charts            │   │
│  │  - Authentication: Placeholder (ready for Azure AD)       │   │
│  │  - URL: http://10.0.160.5:5000 (admin/admin)             │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                   │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  SSH Access (10.0.160.129:22)                            │   │
│  │                                                            │   │
│  │  SSH Proxy (Paramiko)                                     │   │
│  │  - Source IP: 100.64.0.20 → User: p.mojski               │   │
│  │  - Agent forwarding support (-A flag)                     │   │
│  │  - Session recording (JSON)                               │   │
│  │  - Real-time session tracking 🎯 NEW                     │   │
│  │  - UTMP/WTMP logging (ssh0-ssh99) 🎯 NEW                │   │
│  │  - Backend: 10.0.160.4 (Linux SSH)                        │   │
│  │  - Access Control V2: Policy-based authorization          │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                   │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  RDP Access (10.0.160.129:3389)                           │   │
│  │                                                            │   │
│  │  RDP Guard Proxy (Python asyncio)                         │   │
│  │  - Source IP: 100.64.0.39 → User: p.mojski.win           │   │
│  │  - Access control + audit logging                         │   │
│  │  - Forwards to: PyRDP MITM (localhost:13389)             │   │
│  │                                                            │   │
│  │  PyRDP MITM (localhost:13389)                             │   │
│  │  - Full session recording (.pyrdp files)                  │   │
│  │  - Real-time session tracking 🎯 NEW                     │   │
│  │  - UTMP/WTMP logging (rdp0-rdp99) 🎯 NEW                │   │
│  │  - Connection multiplexing detection 🎯 NEW              │   │
│  │  - Backend: 10.30.0.140 (Windows RDP)                     │   │
│  │  - Access Control V2: Policy-based authorization          │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                   │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  Core Components                                          │   │
│  │                                                            │   │
│  │  • PostgreSQL Database (Access Control V2 Schema)         │   │
│  │    - users (username, email, is_active)                  │   │
│  │    - user_source_ips (multiple IPs per user) ⭐         │   │
│  │    - servers (name, address, protocols, is_active)       │   │
│  │    - server_groups (tags/groups) ⭐                      │   │
│  │    - server_group_members (N:M relationships) ⭐         │   │
│  │    - access_policies (flexible permissions) ⭐           │   │
│  │    - policy_ssh_logins (SSH restrictions) ⭐             │   │
│  │    - ip_allocations (proxy IP assignments)               │   │
│  │    - session_recordings (file paths)                     │   │
│  │    - audit_logs (all actions logged)                     │   │
│  │    - sessions (real-time tracking) 🎯 NEW               │   │
│  │                                                            │   │
│  │  • Access Control Engine V2 ⭐                           │   │
│  │    - Policy-based authorization (group/server/service)   │   │
│  │    - Multiple source IPs per user                         │   │
│  │    - Protocol filtering (ssh/rdp/both)                    │   │
│  │    - SSH login restrictions                               │   │
│  │    - Temporal validation (start/end time)                 │   │
│  │    - Legacy fallback for V1 compatibility                 │   │
│  │                                                            │   │
│  │  • Session Monitoring System 🎯 NEW                     │   │
│  │    - Database tracking (18-field sessions table)         │   │
│  │    - UTMP/WTMP integration (system logging)              │   │
│  │    - Custom `jw` command (view active sessions)          │   │
│  │    - Duration/recording size auto-calculation            │   │
│  │    - SSH subsystem & agent detection                      │   │
│  │    - RDP multiplexing support (10s window)               │   │
│  │                                                            │   │
│  │  • IP Pool Manager                                        │   │
│  │    - Pool: 10.0.160.128/25 (126 usable IPs)             │   │
│  │    - Dynamic allocation for backend servers               │   │
│  │    - Release on grant expiration                          │   │
│  │                                                            │   │
│  │  • CLI Management Tool (Typer + Rich) ⭐                 │   │
│  │    - V2 Commands: add-user-v2, add-server-group,         │   │
│  │      grant-access-v2, list-users-v2, etc.                │   │
│  │    - Legacy V1 commands still supported                   │   │
│  │    - `jw` command: View active proxy sessions 🎯 NEW    │   │
│  │                                                            │   │
│  │  • Web Management Interface (Flask) ⭐ NEW               │   │
│  │    - Complete CRUD for users, servers, groups, policies  │   │
│  │    - Dashboard with monitoring and charts                 │   │
│  │    - Active Sessions widget (real-time) 🎯 NEW          │   │
│  │    - Audit log viewer with pagination and filters         │   │
│  │    - Policy wizard with flexible grant scopes             │   │
│  └──────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
                              │
                              │
        ┌─────────────────────┼─────────────────────┐
        │                     │                     │
        ▼                     ▼                     ▼
┌──────────────┐      ┌──────────────┐     ┌──────────────┐
│   Client 1   │      │   Client 2   │     │   Client 3   │
│ 100.64.0.20  │      │ 100.64.0.39  │     │ 100.64.0.88  │
│              │      │              │     │              │
│ p.mojski     │      │p.mojski.win  │     │ (no grant)   │
│ SSH access   │      │ RDP access   │     │ DENIED       │
└──────────────┘      └──────────────┘     └──────────────┘
```

## Technology Stack

### System
- **OS**: Debian 13 (35GB disk, expanded from 3GB)
- **Python**: 3.13 with virtualenv at `/opt/jumphost/venv`
- **Database**: PostgreSQL 17 with SQLAlchemy ORM
- **Alembic**: Database migrations (V2 schema: 8419b886bc6d)

### Web Interface (NEW in v1.1)
- **Flask 3.1.2**: Web framework with Blueprint architecture
- **Flask-Login 0.6.3**: User session management
- **Flask-WTF 1.2.2**: Form handling with CSRF protection
- **Flask-Cors 6.0.2**: API endpoint support
- **Bootstrap 5.3.0**: Frontend CSS framework (CDN)
- **Bootstrap Icons 1.11.0**: Icon library (CDN)
- **Chart.js 4.4.0**: Statistics charts (CDN)
- **Features**:
  - Dashboard with service monitoring
  - User/Server/Group/Policy CRUD operations
  - Policy wizard with flexible scopes
  - Audit log viewer with pagination
  - Connection charts (hourly, by user)
  - Responsive mobile-friendly design

### SSH Proxy
- **Paramiko 4.0.0**: SSH server/client implementation
- **Features**:
  - SSH agent forwarding (AgentServerProxy)
  - PTY forwarding with term type/dimensions
  - Exec/subsystem support (SCP, SFTP)
  - Password + public key authentication
  - Session recording (JSON format)

### RDP Proxy
- **PyRDP MITM 2.1.0**: RDP man-in-the-middle with session recording
- **Twisted 25.5.0**: Async networking framework
- **Custom Guard Proxy**: Python asyncio TCP proxy with access control
- **Patch Applied**: RDPVersion._missing_() for new Windows RDP clients
  - File: `/opt/jumphost/venv/lib/python3.13/site-packages/pyrdp/enum/rdp.py`
  - Handles unknown RDP version numbers
  - Added RDP10_12 = 0x80011

## Access Control Logic

### SSH Access Control
1. Client connects with username + source IP
2. `AccessControlEngine.check_access(db, source_ip, username)`
3. Validates:
   - User exists and is active
   - Source IP matches user's registered source_ip
   - Active grant exists (start_time <= now <= end_time)
   - Target server is active
4. If OK: Connect to backend with agent forwarding
5. If DENIED: Close connection, log to audit_logs

### RDP Access Control (Two-Stage)
1. **Stage 1 - Guard Proxy** (`rdp_guard.py`):
   - Client connects from source IP
   - `AccessControlEngine.check_access(db, source_ip, username=None)`
   - Validates:
     - User found by source_ip
     - Active grant exists
     - Grant's server matches THIS proxy's target_server
   - If OK: Forward to PyRDP MITM on localhost:13389
   - If DENIED: Send "ACCESS DENIED" message, close, log to audit_logs

2. **Stage 2 - PyRDP MITM** (with Session Tracking ⭐):
   - Receives connection from guard proxy
   - Performs full RDP MITM
   - Records session to `.pyrdp` files
   - Connects to backend Windows server
   - Creates/closes Session records in database
   - Tracks session duration and recording file size

## File Structure

```
/opt/jumphost/
├── venv/                           # Python virtual environment
├── src/
│   ├── core/
│   │   ├── database.py            # SQLAlchemy models
│   │   ├── access_control.py      # Access control engine
│   │   └── ip_pool.py             # IP pool manager
│   ├── proxy/
│   │   ├── ssh_proxy.py           # SSH proxy server (WORKING ✓)
│   │   ├── rdp_guard.py           # RDP guard proxy (WORKING ✓)
│   │   ├── rdp_wrapper.sh         # PyRDP MITM wrapper
│   │   └── rdp_proxy.py           # Old Python wrapper (deprecated)
│   └── cli/
│       └── jumphost_cli.py        # CLI management tool
├── certs/                         # SSL certificates for RDP
└── logs/

/var/log/jumphost/
├── ssh_proxy.log                  # SSH proxy logs
├── rdp_guard.log                  # RDP guard proxy logs
├── rdp_wrapper.log                # PyRDP backend logs
├── ssh_recordings/                # SSH session recordings (JSON)
│   └── ssh_session_*.json
└── rdp_recordings/                # RDP session recordings
    ├── replays/                   # .pyrdp replay files
    ├── files/                     # Transferred files
    └── certs/                     # Auto-generated certificates
```

## Database Schema

### users
- `id` (PK), `username`, `email`, `full_name`
- `source_ip` (VARCHAR 45) - Client source IP address
- `is_active`, `created_at`, `updated_at`

### servers
- `id` (PK), `name`, `ip_address`, `os_type`
- `description`, `is_active`, `created_at`, `updated_at`

### access_grants
- `id` (PK), `user_id` (FK), `server_id` (FK)
- `protocol` ('ssh' or 'rdp')
- `start_time`, `end_time` - Temporal access window
- `is_active`, `created_at`

### ip_allocations
- `id` (PK), `ip_address`, `server_id` (FK)
- `allocated_at`, `released_at`

### session_recordings
- `id` (PK), `user_id` (FK), `server_id` (FK)
- `protocol`, `file_path`, `duration`, `started_at`, `ended_at`

### audit_logs
- `id` (PK), `user_id` (FK nullable)
- `action` (e.g., 'ssh_access_granted', 'rdp_access_denied')
- `resource_type`, `resource_id`, `source_ip`
- `success` (Boolean), `details` (TEXT), `timestamp`

### sessions (NEW in v1.1) ⭐
Real-time session tracking for active and historical connections:
- `id` (PK), `session_id` (unique) - Session identifier
- `user_id` (FK), `server_id` (FK), `protocol` ('ssh' or 'rdp')
- `source_ip`, `proxy_ip`, `backend_ip`, `backend_port`
- `ssh_username` - SSH login used for connection
- `subsystem_name` - Subsystem type (sftp, scp, etc.)
- `ssh_agent_used` - Boolean flag if SSH agent forwarding was used
- `started_at`, `ended_at`, `duration_seconds`
- `is_active` - TRUE for active sessions, FALSE for closed
- `termination_reason` - 'normal', 'error', 'timeout', 'killed'
- `recording_path`, `recording_size` - Session recording details
- `policy_id` (FK) - Policy that granted access
- `created_at`

**Features:**
- Real-time tracking of SSH and RDP connections ⭐
- Automatic session start on successful backend authentication
- Automatic session close on disconnect (normal or error)
- Duration calculation in seconds
- Recording file path and size tracking
- SSH agent detection and subsystem tracking (sftp, scp)
- RDP session recording with PyRDP integration
- Visible in Web GUI Dashboard "Active Sessions"

**SSH Proxy Integration:**
- Creates session record after backend authentication
- Updates session on disconnect (via channel close handler)
- Tracks SSH username, subsystem (sftp/scp), SSH agent usage
- Records session duration and file size on close

**RDP Proxy Integration (PyRDP MITM):**
- Creates session record after access control check
- Uses TCP layer observer pattern for disconnect detection
- Deduplikacja: RDP clients open multiple connections (10s window)
- Client and Server disconnection observers for reliable cleanup
- Records session duration and .pyrdp file size on close
- Multiple concurrent sessions supported independently
- Updates on normal close: `ended_at`, `duration_seconds`, `recording_size`
- Updates on error: `termination_reason='error'`
- Logs all session events to `/var/log/jumphost/ssh_proxy.log`

## Current Network Configuration

### Management
- Management SSH: `10.0.160.5:22` (OpenSSH sshd)

### Proxy Endpoints (Current - Same IP!)
- SSH Proxy: `10.0.160.129:22` → Backend: `10.0.160.4:22`
- RDP Guard: `10.0.160.129:3389` → PyRDP → Backend: `10.30.0.140:3389`
- PyRDP Backend: `localhost:13389` (internal)

### Backend Servers
- Linux SSH: `10.0.160.4:22`
- Windows RDP: `10.30.0.140:3389`

### Clients
- `100.64.0.20` - p.mojski (Linux, SSH grant to 10.0.160.4)
- `100.64.0.39` - p.mojski.win (Windows, RDP grant to 10.30.0.140)

### IP Pool (Not Yet Used)
- Range: `10.0.160.128/25` (10.0.160.129 - 10.0.160.254)
- Total: 126 usable IPs
- Reserved: 10.0.160.129 (currently used for both SSH and RDP - ISSUE!)

## CLI Usage Examples

```bash
# Add user with source IP
/opt/jumphost/venv/bin/python src/cli/jumphost_cli.py add-user p.mojski

# Add servers
/opt/jumphost/venv/bin/python src/cli/jumphost_cli.py add-server linux-ssh 10.0.160.4 linux
/opt/jumphost/venv/bin/python src/cli/jumphost_cli.py add-server win-rdp 10.30.0.140 windows

# Grant access for 2 hours
/opt/jumphost/venv/bin/python src/cli/jumphost_cli.py grant-access p.mojski 10.0.160.4 --duration 120

# List grants
/opt/jumphost/venv/bin/python src/cli/jumphost_cli.py list-grants
```

## Session Recording

### SSH Sessions
- Format: JSON with timestamp and I/O events
- Location: `/var/log/jumphost/ssh_recordings/ssh_session_*.json`
- Content: PTY input/output, commands, timing

### RDP Sessions
- Format: PyRDP replay files (.pyrdp)
- Location: `/var/log/jumphost/rdp_recordings/replays/`
- Playback: `pyrdp-player replay_file.pyrdp`
- Features: Full video replay, file transfers, clipboard

## Tested & Working Features

### SSH Proxy ✓
- [x] Password authentication
- [x] Public key authentication
- [x] SSH agent forwarding (-A flag, tracked in session metadata) ⭐
- [x] PTY forwarding (term type, dimensions)
- [x] Shell sessions
- [x] Exec requests (SCP, tracked in session metadata) ⭐
- [x] Subsystem requests (SFTP, tracked in session metadata) ⭐
- [x] Session recording (JSON)
- [x] Source IP-based access control
- [x] Temporal access validation
- [x] Real-time session monitoring 🎯
- [x] UTMP/WTMP logging (ssh0-ssh99) 🎯

### RDP Proxy ✓
- [x] PyRDP MITM with session recording and real-time tracking ⭐
- [x] Guard proxy with access control
- [x] Source IP-based access control
- [x] Backend server verification
- [x] Audit logging (access granted/denied)
- [x] Session recording (.pyrdp files)
- [x] RDP version compatibility patch (RDP10_12)
- [x] Access denial with message
- [x] Real-time session monitoring in Web GUI ⭐
- [x] Connection multiplexing detection (10s window) 🎯
- [x] UTMP/WTMP logging (rdp0-rdp99) 🎯

### Session Monitoring & Logging 🎯 (NEW in v1.1)
- [x] Real-time session tracking in database (sessions table with 18 fields)
- [x] Web GUI "Active Sessions" dashboard widget (7-column table)
- [x] UTMP/WTMP integration (system login records)
- [x] Custom `jw` command for viewing active proxy sessions
- [x] Session duration auto-calculation
- [x] Recording file path and size tracking
- [x] SSH subsystem detection (sftp, scp, shell)
- [x] SSH agent forwarding detection
- [x] RDP connection multiplexing support
- [x] Multiple concurrent sessions (tested with 4+ simultaneous connections)
- [x] Reliable session closing via TCP observer pattern

## Known Issues & Limitations

### Architecture Issues
1. **IP Pool Not Used**: Dynamic allocation not yet implemented
   - Currently manual IP assignment
   - Need automated allocation on grant creation
   - Need automatic cleanup on grant expiration

2. **No FreeIPA Integration**: Using local database for users
   - Planned: Sync users from FreeIPA
   - Planned: FreeIPA authentication backend

### Minor Issues
1. Source IP must be manually set in database (CLI doesn't support it)
2. No monitoring/alerting
3. No systemd service files
4. SSH proxy runs on port 22, conflicts with management SSH
5. UTMP entries not shown in 'w' command (no real PTY) - use `jw` instead

## Performance & Scaling

### Current Limits
- SSH: Paramiko handles ~100 concurrent connections
- RDP: PyRDP MITM tested with ~20 concurrent sessions
- Database: PostgreSQL with indexes on is_active, started_at
- Session tracking: Tested with 4+ simultaneous connections

### Future Optimizations
- Connection pooling for database
- Separate SSH proxy instances per backend
- Load balancing for multiple jump hosts

## Security Considerations

### Current
- Source IP validation
- Temporal access control (start/end time)
- Session recording for audit
- Backend server verification

### Missing (TODO)
- TLS for RDP connections
- SSH host key verification
- Rate limiting / DDoS protection
- Security hardening (SELinux, AppArmor)
- Log rotation
- Encrypted session recordings

## Maintenance

### Start Services
```bash
# SSH Proxy
cd /opt/jumphost && sudo /opt/jumphost/venv/bin/python src/proxy/ssh_proxy.py &

# RDP Backend (PyRDP MITM)
sudo /opt/jumphost/src/proxy/rdp_wrapper.sh &

# RDP Guard (Access Control)
cd /opt/jumphost && sudo /opt/jumphost/venv/bin/python src/proxy/rdp_guard.py &

# Web GUI (Development)
cd /opt/jumphost/src/web && /opt/jumphost/venv/bin/python app.py &

# Web GUI (Production with gunicorn)
cd /opt/jumphost/src/web && /opt/jumphost/venv/bin/gunicorn --bind 0.0.0.0:5000 --workers 4 app:app &
```

### Stop Services
```bash
sudo pkill -f ssh_proxy
sudo pkill -f rdp_wrapper
sudo pkill -f rdp_guard
pkill -f "python.*app.py"
pkill -f gunicorn
```

### View Logs
```bash
tail -f /var/log/jumphost/ssh_proxy.log
tail -f /var/log/jumphost/rdp_guard.log
tail -f /var/log/jumphost/rdp_wrapper.log
tail -f /tmp/flask.log  # Web GUI logs
```

### Check Audit Logs
```bash
# Via CLI
cd /opt/jumphost && /opt/jumphost/venv/bin/python -c "
from src.core.database import SessionLocal, AuditLog
db =Web GUI Tests
- [x] Login with admin/admin
- [x] Dashboard loads with service status
- [x] Dashboard shows statistics cards
- [x] Dashboard auto-refreshes every 30 seconds
- [x] User list page loads
- [x] Add new user with multiple source IPs
- [x] View user details with policies
- [x] Edit user information
- [x] Delete user
- [x] Server list page loads
- [x] Add new server with IP allocation
- [x] View server details with groups
- [x] Edit server information
- [x] Delete server
- [x] Group list page loads
- [x] Create new group
- [x] View group with members
- [x] Add server to group
- [x] Remove server from group
- [x] Delete group
- [x] Policy list page loads with filters
- [x] Grant access wizard (group scope)
- [x] Grant access wizard (server scope)
- [x] Grant access wizard (service scope)
- [x] Revoke policy
- [x] Delete policy
- [x] Monitoring page loads with charts
- [x] Audit log viewer with pagination
- [x] Audit log filters work
- [x] Logout works
- [x] Session persistence across requests

###  SessionLocal()
logs = db.query(AuditLog).order_by(AuditLog.timestamp.desc()).limit(10).all()
for log in logs:
    print(f'{log.timestamp} - {log.action} - {log.source_ip} - {log.success} - {log.details}')
db.close()
"

# Via Web GUI
# Navigate to: http://10.0.160.5:5000/monitoring/audit
# Login: admin / admin
# Use filters to search logs
```

### Access Web GUI
```bash
# Development (direct Python)
cd /opt/jumphost/src/web
/opt/jumphost/venv/bin/python app.py
# Access: http://10.0.160.5:5000
# Login: admin / admin

# Production (with gunicorn)
cd /opt/jumphost/src/web
/opt/jumphost/venv/bin/gunicorn --bind 0.0.0.0:5000 --workers 4 app:app
# Access: http://10.0.160.5:5000
```

### Web GUI Operations
```bash
# View dashboard
curl -u admin:admin http://localhost:5000/

# Get stats API
curl http://localhost:5000/dashboard/api/stats

# Get hourly connection chart data
curl http://localhost:5000/monitoring/api/stats/hourly

# Get top users chart data
curl http://localhost:5000/monitoring/api/stats/by_user
```

## Testing Checklist

### SSH Proxy Tests
- [x] Connect with password
- [x] Connect with SSH key
- [x] Connect with agent forwarding (`ssh -A`)
- [x] Copy files with SCP
- [x] Transfer files with SFTP
- [x] Check session recording files
- [x] Test access denial (wrong source IP)
- [x] Test expired grant

### RDP Proxy Tests
- [x] Connect from allowed source IP
- [x] Test access denial (wrong source IP)
- [x] Test access denial (grant for different backend)
- [x] Check .pyrdp recording files
- [x] Replay session with pyrdp-player
- [x] Check audit logs in database

## Contributing

When modifying the codebase:
1. Test both SSH and RDP proxies
2. Verify audit logs are written correctly
3. Check session recordings are created
4. Update this documentation
5. Update ROADMAP.md with progress

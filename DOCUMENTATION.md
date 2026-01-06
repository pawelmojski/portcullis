# Jump Host - SSH/RDP Proxy with Access Control

## Project Overview

Self-made SSH/RDP jump host with temporal access control, source IP mapping, session recording, real-time monitoring, and system logging integration.

## Quick Links

- **Installation Guide**: [INSTALL.md](INSTALL.md) - Complete setup instructions
- **PyRDP Patches (Main Venv)**: [PYRDP_PATCHES_MAIN_VENV.md](PYRDP_PATCHES_MAIN_VENV.md) - Access control integration
- **PyRDP Patches (Converter Venv)**: [PYRDP_PATCHES.md](PYRDP_PATCHES.md) - MP4 conversion patches
- **Patch Files**: [patches/](patches/) - Unified diff files for automated application
- **Roadmap**: [ROADMAP.md](ROADMAP.md) - Development history and future plans
- **Dependencies**: See [requirements.txt](requirements.txt) and [requirements-pyrdp-converter.txt](requirements-pyrdp-converter.txt)

## Architecture (Current State - v1.5)

```
┌─────────────────────────────────────────────────────────────────┐
│                         JUMP HOST                                │
│                      (10.0.160.5)                                │
│                                                                   │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  Web Management Interface (5000) - Systemd Service 🎯   │   │
│  │                                                            │   │
│  │  Flask Web GUI (Bootstrap 5)                              │   │
│  │  - Dashboard: Auto-refresh stats, active sessions 🎯     │   │
│  │  - Session History: List, filter, live view 🎯          │   │
│  │  - Live Session Viewer: Real-time SSH log streaming 🎯  │   │
│  │  - RDP Session Viewer: MP4 conversion & video player 🎯 │   │
│  │  - User Management: CRUD + multiple source IPs            │   │
│  │  - Server Management: CRUD + IP allocation                │   │
│  │  - Group Management: Create groups, assign servers        │   │
│  │  - Policy Wizard: Grant access with flexible scopes       │   │
│  │  - Monitoring: Audit logs with filters, charts            │   │
│  │  - Authentication: Placeholder (ready for Azure AD)       │   │
│  │  - URL: http://10.0.160.5:5000 (admin/admin)             │   │
│  │  - Service: jumphost-flask.service                        │   │
│  │  - Logs: /var/log/jumphost/flask.log                      │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                   │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  SSH Access (10.0.160.129:22) - Systemd Service 🎯      │   │
│  │                                                            │   │
│  │  SSH Proxy (Paramiko)                                     │   │
│  │  - Source IP: 100.64.0.20 → User: p.mojski               │   │
│  │  - Agent forwarding support (-A flag)                     │   │
│  │  - Live session recording (JSONL) 🎯 NEW                │   │
│  │  - Real-time session tracking 🎯                         │   │
│  │  - Grant expiry auto-disconnect 🎯 NEW v1.5             │   │
│  │  - Wall-style warnings (5 min, 1 min) 🎯 NEW v1.5      │   │
│  │  - UTMP/WTMP logging (ssh0-ssh99)                        │   │
│  │  - Backend: 10.0.160.4 (Linux SSH)                        │   │
│  │  - Access Control V2: Policy-based authorization          │   │
│  │  - Service: jumphost-ssh-proxy.service                    │   │
│  │  - Logs: /var/log/jumphost/ssh_proxy.log                  │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                   │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  RDP Access (0.0.0.0:3389) - Systemd Service 🎯         │   │
│  │                                                            │   │
│  │  PyRDP MITM (Direct)                                      │   │
│  │  - Listen: 0.0.0.0:3389                                   │   │
│  │  - Target: 127.0.0.1:3389 (dynamic routing)              │   │
│  │  - Full session recording (.pyrdp files)                  │   │
│  │  - Real-time session tracking 🎯                         │   │
│  │  - UTMP/WTMP logging (rdp0-rdp99)                        │   │
│  │  - Connection multiplexing detection                      │   │
│  │  - Access Control V2: Policy-based authorization          │   │
│  │  - Service: jumphost-rdp-proxy.service                    │   │
│  │  - Logs: /var/log/jumphost/rdp_mitm.log                   │   │
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
│  │    - sessions (real-time tracking) 🎯                   │   │
│  │                                                            │   │
│  │  • Access Control Engine V2 ⭐                           │   │
│  │    - Policy-based authorization (group/server/service)   │   │
│  │    - Multiple source IPs per user                         │   │
│  │    - Protocol filtering (ssh/rdp/both)                    │   │
│  │    - SSH login restrictions                               │   │
│  │    - Temporal validation (start/end time)                 │   │
│  │    - Legacy fallback for V1 compatibility                 │   │
│  │                                                            │   │
│  │  • Session Monitoring System 🎯                         │   │
│  │    - Database tracking (18-field sessions table)         │   │
│  │    - UTMP/WTMP integration (system logging)              │   │
│  │    - Custom `jw` command (view active sessions)          │   │
│  │    - Duration/recording size auto-calculation            │   │
│  │    - SSH subsystem & agent detection                      │   │
│  │    - RDP multiplexing support (10s window)               │   │
│  │    - Live session recording (JSONL format) 🎯          │   │
│  │    - Web GUI live view with 2s polling 🎯              │   │
│  │                                                            │   │
│  │  • MP4 Conversion System 🎯 NEW v1.3                   │   │
│  │    - Background worker queue (2 workers, systemd)        │   │
│  │    - PyRDP converter with PySide6 (separate venv)        │   │
│  │    - On-demand .pyrdp → .mp4 conversion (10 FPS)        │   │
│  │    - Queue management: 2 concurrent, 10 pending max      │   │
│  │    - Priority "rush" button for urgent conversions       │   │
│  │    - Progress tracking with ETA calculation              │   │
│  │    - HTML5 video player with seeking                     │   │
│  │    - MP4 cache: /var/log/jumphost/rdp_recordings/        │   │
│  │      mp4_cache/                                           │   │
│  │    - Workers: jumphost-mp4-converter@1/2.service         │   │
│  │    - Resource limits: 150% CPU, 2GB RAM per worker       │   │
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
│  │    - `jw` command: View active proxy sessions 🎯       │   │
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
│   │   ├── access_control.py      # Access control engine V2
│   │   └── ip_pool.py             # IP pool manager
│   ├── proxy/
│   │   ├── ssh_proxy.py           # SSH proxy server (Systemd) ✓
│   │   └── [RDP] Direct PyRDP MITM (Systemd) ✓
│   ├── cli/
│   │   └── jumphost_cli.py        # CLI management tool
│   └── web/
│       ├── app.py                 # Flask application (Systemd) ✓
│       ├── blueprints/
│       │   ├── dashboard.py       # Dashboard + API endpoints
│       │   ├── sessions.py        # Session history & live view 🎯
│       │   ├── users.py           # User management
│       │   ├── servers.py         # Server management
│       │   ├── groups.py          # Group management
│       │   ├── policies.py        # Policy wizard
│       │   └── monitoring.py      # Audit logs
│       └── templates/             # Jinja2 templates
├── certs/                         # SSL certificates for RDP
└── scripts/                       # Utility scripts

/var/log/jumphost/
├── flask.log                      # Flask web app logs 🎯
├── ssh_proxy.log                  # SSH proxy logs 🎯
├── rdp_mitm.log                   # PyRDP MITM logs 🎯
├── mp4-converter-worker1.log      # MP4 worker 1 logs 🎯
├── mp4-converter-worker2.log      # MP4 worker 2 logs 🎯
├── ssh_recordings/                # SSH session recordings (JSONL) 🎯
│   └── ssh_session_*.log          # Live recording format
└── rdp_recordings/                # RDP session recordings
    ├── replays/                   # .pyrdp replay files
    ├── files/                     # Transferred files
    ├── certs/                     # Auto-generated certificates
    ├── json_cache/                # JSON metadata cache (RDP events)
    └── mp4_cache/                 # MP4 video cache 🎯 NEW

/etc/systemd/system/
├── jumphost-flask.service         # Flask web service 🎯
├── jumphost-ssh-proxy.service     # SSH proxy service 🎯
├── jumphost-rdp-proxy.service     # RDP proxy service 🎯
└── jumphost-mp4-converter@.service # MP4 worker template (@1, @2) 🎯 NEW

/etc/logrotate.d/
└── jumphost                       # Log rotation config 🎯
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
- **Live SSH Session Viewer**: Real-time log streaming with 2s polling 🎯
- **Session History**: Filter by protocol, user, server, status 🎯

**SSH Proxy Integration:**
- Creates session record after backend authentication
- Updates session on disconnect (via channel close handler)
- Tracks SSH username, subsystem (sftp/scp), SSH agent usage
- Records session duration and file size on close
- **JSONL Recording**: Streams events immediately to disk (not buffered) 🎯
- **Live View Support**: Web GUI polls for new events every 2 seconds 🎯

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
- **RDP Viewer** (v1.2-dev): Metadata extraction, JSON conversion, MP4 planned 🔄

## Session Viewer Features (v1.1+)

### SSH Live View
- **Real-time Streaming**: JSONL format, 2-second polling
- **Terminal UI**: Dark theme, monospace font, color-coded events
- **Event Types**: Connection, authentication, server output, client input, disconnect
- **Filters**: Search text, toggle client/server messages
- **Auto-scroll**: Keeps latest events visible
- **Download**: Export session .log file

### RDP Session Review (v1.2-dev)
- **Metadata Display**: Host, resolution, username, domain, duration
- **Event Statistics**: Keyboard keystrokes, mouse events count
- **JSON Conversion**: `pyrdp-convert -f json` with caching
- **Download Support**: Original .pyrdp file for pyrdp-player
- **Playback Instructions**: How to view locally with PyRDP Player
- **Future (MP4)**: Embedded video player after CPU upgrade 🔜

**Cache System**:
- JSON cache: `/var/log/jumphost/rdp_recordings/json_cache/`
- On-demand conversion with mtime checking
- Avoids repeated subprocess calls
- Owned by Flask user (p.mojski)

**Limitations**:
- MP4 conversion requires CPU with SSSE3/SSE4 support
- Current VM: "Common KVM processor" (basic instruction set)
- Solution: Proxmox CPU upgrade to `host` type
- JSON events show input only (no screen updates)

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

## SSH Port Forwarding (v1.4+) 🎯

### Local Forward (-L)
Forward local port through jump to backend destination:
```bash
# Forward local 2222 to backend SSH (via jump)
ssh -A -L 2222:backend.local:22 p.mojski@10.0.160.129

# In another terminal
ssh -p 2222 user@localhost  # Connects to backend through jump

# Forward local 8080 to backend web server
ssh -A -L 8080:backend.local:80 p.mojski@10.0.160.129
curl http://localhost:8080  # Access backend web via jump
```

### Remote Forward (-R)
Make local port accessible on backend (exits from backend):
```bash
# Make client's localhost:8080 accessible on backend:9090
ssh -A -R 9090:localhost:8080 p.mojski@10.0.160.129

# On client, start HTTP server
python3 -m http.server 8080

# On backend
curl localhost:9090  # Gets data from client's HTTP server

# Forward external service through client
ssh -A -R 9093:external.com:25 p.mojski@10.0.160.129
# Backend can now telnet localhost:9093 to reach external.com:25 via client
```

### Dynamic SOCKS (-D)
Use jump+backend as SOCKS proxy (exits from backend):
```bash
# Start SOCKS proxy on localhost:8123
ssh -A -D 8123 p.mojski@10.0.160.129

# Use SOCKS proxy with curl
curl --socks5 localhost:8123 http://example.com

# Use SOCKS proxy with Firefox
# Preferences → Network Settings → Manual proxy
# SOCKS Host: localhost, Port: 8123, SOCKS v5

# Use with proxychains
# Edit /etc/proxychains.conf: socks5 127.0.0.1 8123
proxychains wget http://example.com
```

### Permission Requirements
Port forwarding requires `port_forwarding_allowed=True` in access policy:
```python
# Enable in database
policy.port_forwarding_allowed = True

# Or via Web GUI (Policies → Add/Edit)
# Check "Allow Port Forwarding" checkbox
```

### Architecture Notes
- **-L**: Standard direct-tcpip, jump forwards to backend
- **-R**: Cascaded architecture via pool IP binding
  - Jump opens listener on pool IP (e.g. 10.0.160.129:9090)
  - Backend requests -R to jump's pool IP
  - Traffic: Backend → Jump pool IP → Jump localhost → Client
- **-D**: Client parses SOCKS, sends direct-tcpip per connection
- **Pool IP**: Each session gets unique IP, allows multiple backends same ports

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
- [x] Live session recording (JSONL format) 🎯
- [x] Source IP-based access control
- [x] Temporal access validation
- [x] Real-time session monitoring 🎯
- [x] UTMP/WTMP logging (ssh0-ssh99) 🎯
- [x] Systemd service with auto-restart 🎯
- [x] **SSH Port Forwarding** 🎯 NEW (v1.4)
  - [x] Local forward (-L): `ssh -L 2222:backend:22 user@jump`
  - [x] Remote forward (-R): `ssh -R 9090:localhost:8080 user@jump`
  - [x] Dynamic SOCKS (-D): `ssh -D 8123 user@jump`
  - [x] Per-policy permission control (`port_forwarding_allowed` flag)
  - [x] Cascaded -R architecture (jump pool IP → backend → client)
  - [x] Pool IP binding for multi-backend support
- [x] **Grant Expiry Auto-Disconnect** 🎯 NEW (v1.5)
  - [x] Automatic session termination when grant expires
  - [x] Wall-style warnings (5 min, 1 min before expiry)
  - [x] Welcome message showing grant validity
  - [x] Only for interactive shell sessions (not SCP/SFTP)
  - [x] Enhanced grant form (minutes, datetime pickers, UTC)

### RDP Proxy ✓
- [x] PyRDP MITM with session recording and real-time tracking ⭐
- [x] Direct MITM on 0.0.0.0:3389 (no guard proxy) 🎯 NEW
- [x] Source IP-based access control
- [x] Backend server verification
- [x] Audit logging (access granted/denied)
- [x] Session recording (.pyrdp files)
- [x] RDP version compatibility patch (RDP10_12)
- [x] Access denial with message
- [x] Real-time session monitoring in Web GUI ⭐
- [x] Connection multiplexing detection (10s window) 🎯
- [x] UTMP/WTMP logging (rdp0-rdp99) 🎯
- [x] Systemd service with auto-restart 🎯 NEW

### Session Monitoring & Logging 🎯 (NEW in v1.1)
- [x] Real-time session tracking in database (sessions table with 18 fields)
- [x] Web GUI "Active Sessions" dashboard widget (auto-refresh every 5s) 🎯 NEW
- [x] Session history with filtering (protocol, status, user, server) 🎯 NEW
- [x] Live session viewer with terminal UI (SSH) 🎯 NEW
- [x] 2-second polling for active session logs 🎯 NEW
- [x] JSONL format for streaming session recording 🎯 NEW
- [x] LRU cache for session parser (performance optimization) 🎯 NEW
- [x] UTMP/WTMP integration (system login records)
- [x] Custom `jw` command for viewing active proxy sessions
- [x] Session duration auto-calculation
- [x] Recording file path and size tracking
- [x] SSH subsystem detection (sftp, scp, shell)
- [x] SSH agent forwarding detection
- [x] RDP connection multiplexing support
- [x] Multiple concurrent sessions (tested with 4+ simultaneous connections)
- [x] Reliable session closing via TCP observer pattern
- [x] Download recordings (SSH .log, RDP .pyrdp) 🎯 NEW

### RDP Session MP4 Conversion 🎯 (NEW in v1.3)
- [x] Background worker queue system (2 systemd workers) 🎯 NEW
- [x] On-demand .pyrdp → .mp4 conversion (10 FPS) 🎯 NEW
- [x] Queue management (max 2 concurrent, 10 pending) 🎯 NEW
- [x] Priority "rush" button for urgent conversions 🎯 NEW
- [x] Real-time progress tracking with ETA 🎯 NEW
- [x] HTML5 video player with seeking support 🎯 NEW
- [x] MP4 download button 🎯 NEW
- [x] Frontend polling (2s interval) for conversion status 🎯 NEW
- [x] MP4 cache management (/var/log/jumphost/rdp_recordings/mp4_cache/) 🎯 NEW
- [x] Separate PyRDP environment with PySide6 🎯 NEW
- [x] Worker resource limits (150% CPU, 2GB RAM) 🎯 NEW
- [x] RDP version compatibility (RDP10_12 = 0x80011) 🎯 NEW
- [x] Python 3.13 compatibility fixes 🎯 NEW
- [x] Database queue table (mp4_conversion_queue) 🎯 NEW
- [x] API endpoints: convert, status, stream, priority, delete 🎯 NEW

### Web Management Interface 🎯 (NEW in v1.1)
- [x] Dashboard with service status and statistics
- [x] Auto-refresh dashboard (5s interval) 🎯 NEW
- [x] Active sessions monitoring with live updates 🎯 NEW
- [x] Session history viewer with filters 🎯 NEW
- [x] Live SSH session viewer (2s polling) 🎯 NEW
- [x] Terminal-style log viewer (search, filter) 🎯 NEW
- [x] User management (CRUD)
- [x] Server management (CRUD)
- [x] Group management (CRUD)
- [x] Policy wizard (grant access)
- [x] Audit log viewer with filters
- [x] Authentication placeholder
- [x] Bootstrap 5 responsive design
- [x] Systemd service integration 🎯 NEW

### Deployment & Operations 🎯 (NEW in v1.1)
- [x] Systemd service files for all components 🎯 NEW
  - jumphost-flask.service (Flask web app)
  - jumphost-ssh-proxy.service (SSH proxy)
  - jumphost-rdp-proxy.service (RDP proxy via PyRDP MITM)
- [x] Centralized logging in /var/log/jumphost/ 🎯 NEW
- [x] Logrotate configuration (14/30 days retention) 🎯 NEW
- [x] Auto-restart on failure 🎯 NEW
- [x] Proper user permissions (root for ports 22/3389, p.mojski for Flask) 🎯 NEW

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
3. ~~No systemd service files~~ ✓ FIXED in v1.1
4. SSH proxy runs on port 22, conflicts with management SSH
5. UTMP entries not shown in 'w' command (no real PTY) - use `jw` instead

## Performance & Scaling

### Current Limits
- SSH: Paramiko handles ~100 concurrent connections
- RDP: PyRDP MITM tested with ~20 concurrent sessions
- Database: PostgreSQL with indexes on is_active, started_at
- Session tracking: Tested with 4+ simultaneous connections
- Web GUI: LRU cache (maxsize=100) for session parsing

### Future Optimizations
- Connection pooling for database
- Separate SSH proxy instances per backend
- Load balancing for multiple jump hosts
- Redis for session state caching

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
- [x] Dashboard auto-refreshes every 5 seconds 🎯 NEW
- [x] Active sessions update automatically 🎯 NEW
- [x] Statistics update in real-time 🎯 NEW
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
- [x] Session history page loads 🎯 NEW
- [x] Session list filtering works (protocol, status, user, server) 🎯 NEW
- [x] Session detail page shows metadata 🎯 NEW
- [x] Live session viewer works (2s polling) 🎯 NEW
- [x] Recording download works (SSH .log, RDP .pyrdp) 🎯 NEW
- [x] Search in session logs works 🎯 NEW
- [x] Client/Server log filters work 🎯 NEW
- [x] Logout works
- [x] Session persistence across requests

### Systemd Service Management 🎯 (NEW in v1.1)

```bash
# Check service status
sudo systemctl status jumphost-flask
sudo systemctl status jumphost-ssh-proxy
sudo systemctl status jumphost-rdp-proxy

# Start/stop/restart services
sudo systemctl start jumphost-flask
sudo systemctl restart jumphost-ssh-proxy
sudo systemctl stop jumphost-rdp-proxy

# Enable/disable auto-start on boot
sudo systemctl enable jumphost-flask
sudo systemctl disable jumphost-rdp-proxy

# View logs
sudo journalctl -u jumphost-flask -f
sudo journalctl -u jumphost-ssh-proxy --since "1 hour ago"
tail -f /var/log/jumphost/flask.log
tail -f /var/log/jumphost/ssh_proxy.log
tail -f /var/log/jumphost/rdp_mitm.log

# Check all jumphost services
sudo systemctl list-units 'jumphost-*'
```

### Session History & Live View 🎯 (NEW in v1.1)

```bash
# Via CLI - Active sessions
python3 src/cli/jumphost_cli.py sessions --active

# Via system - UTMP/WTMP
jw                    # Custom command showing active sessions
w                     # System command (won't show jumphost sessions)
last -f /var/log/wtmp # Historical sessions

# Via Web GUI
# Navigate to: http://10.0.160.5:5000/sessions/
# - View all sessions (active and closed)
# - Filter by protocol, status, user, server
# - Click "View" to see session details
# - Click "Live View" for active SSH sessions (2s polling)
# - Download recordings (SSH .log, RDP .pyrdp)
# - Search within session logs
# - Toggle Client/Server events

# Via Database
python3 << EOF
import sys; sys.path.insert(0, '/opt/jumphost')
from src.core.database import SessionLocal, Session

db = SessionLocal()
active = db.query(Session).filter_by(is_active=True).all()
for s in active:
    print(f'{s.protocol} | {s.user} → {s.server} | {s.source_ip} | Started: {s.started_at}')
db.close()
EOF
```

### Monitoring & Audit Logs

```bash
# Via CLI
python3 << EOF
import sys; sys.path.insert(0, '/opt/jumphost')
from src.core.database import SessionLocal, AuditLog

db = SessionLocal()
logs = db.query(AuditLog).order_by(AuditLog.timestamp.desc()).limit(10).all()
for log in logs:
    print(f'{log.timestamp} - {log.action} - {log.source_ip} - {log.success} - {log.details}')
db.close()
EOF

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

---

## Installation & Dependencies

### System Requirements

See [INSTALL.md](INSTALL.md) for complete installation instructions.

**Minimum Requirements**:
- OS: Debian 13 or similar
- Python: 3.13+
- PostgreSQL: 17+
- RAM: 4GB (8GB recommended for MP4 conversion)
- Disk: 35GB+ (for recordings)
- CPU: Host passthrough for Qt/PySide6 (ssse3, sse4.1, sse4.2, popcnt)

### APT Packages

```bash
# Core dependencies
sudo apt-get install -y \
    build-essential \
    python3-dev \
    python3-venv \
    postgresql \
    postgresql-contrib \
    libpq-dev \
    git

# Qt dependencies (for MP4 conversion with PySide6)
sudo apt-get install -y \
    libgl1 \
    libglib2.0-0 \
    libegl1 \
    libxkbcommon0 \
    libdbus-1-3 \
    libxcb-xinerama0 \
    libxcb-cursor0 \
    libxcb-icccm4 \
    libxcb-image0 \
    libxcb-keysyms1 \
    libxcb-render-util0
```

### Python Packages

**Main Environment** (`venv/`):
```bash
pip install -r requirements.txt
```

Key packages:
- Flask 3.1.2 - Web framework
- SQLAlchemy 2.0.45 - Database ORM
- Paramiko 4.0.0 - SSH proxy
- pyrdp-mitm 2.1.0 - RDP proxy (without PySide6)
- typer, rich - CLI tools
- psycopg2-binary - PostgreSQL driver

**MP4 Converter Environment** (`venv-pyrdp-converter/`):
```bash
pip install -r requirements-pyrdp-converter.txt
```

Key packages:
- PySide6 6.10.1 - Qt for Python (MP4 rendering)
- av 16.0.1 - Audio/Video processing
- pyrdp-mitm 2.1.0 - RDP converter
- qimage2ndarray 1.10.0 - Image conversion

### PyRDP Patches (Critical!)

**Required**: MP4 conversion will NOT work without these patches.

See [PYRDP_PATCHES.md](PYRDP_PATCHES.md) for detailed instructions.

Three patches required in `venv-pyrdp-converter`:

1. **enum/rdp.py** - Add RDP10_12 version support (Windows 11)
2. **mitm/FileMapping.py** - Python 3.13 compatibility (BinaryIO import)
3. **convert/utils.py** - FPS optimization (fps=10 parameter)

Verify patches:
```bash
cd /opt/jumphost
source venv-pyrdp-converter/bin/activate
grep "RDP10_12" venv-pyrdp-converter/lib/python3.13/site-packages/pyrdp/enum/rdp.py
grep "BinaryIO" venv-pyrdp-converter/lib/python3.13/site-packages/pyrdp/mitm/FileMapping.py
grep "fps=10" venv-pyrdp-converter/lib/python3.13/site-packages/pyrdp/convert/utils.py
```

All three commands must return results.

### Proxmox CPU Configuration (Important!)

For PySide6/Qt to work, VM CPU must support SSE instructions:

```bash
# Edit VM config: /etc/pve/qemu-server/<VMID>.conf
cpu: host

# Or via GUI: VM → Hardware → Processors → CPU Type: host
```

Verify:
```bash
grep -E "ssse3|sse4_1|sse4_2|popcnt" /proc/cpuinfo | head -1
```

If empty, MP4 conversion will segfault.

---

## Contributing

When modifying the codebase:
1. Test both SSH and RDP proxies
2. Verify audit logs are written correctly
3. Check session recordings are created
4. Update this documentation
5. Update ROADMAP.md with progress

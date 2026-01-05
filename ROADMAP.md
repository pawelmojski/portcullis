# Jump Host Project - Roadmap & TODO

## Current Status: v1.4 (Recursive Groups & Enhanced Policies) - January 2026 ✅

**Operational Services:**
- ✅ SSH Proxy: `0.0.0.0:22` (systemd: jumphost-ssh-proxy.service)
- ✅ RDP Proxy: `0.0.0.0:3389` (systemd: jumphost-rdp-proxy.service)  
- ✅ Flask Web: `0.0.0.0:5000` (systemd: jumphost-flask.service)
- ✅ MP4 Workers: 2 instances (systemd: jumphost-mp4-converter@1/2.service)
- ✅ PostgreSQL: Access Control V2 with policy-based authorization
- ✅ Session Monitoring: Real-time tracking with live view (SSH + RDP MP4)
- ✅ Auto-Refresh Dashboard: 5-second updates via AJAX
- ✅ RDP MP4 Conversion: Background queue with progress tracking
- ✅ Recursive User Groups: Hierarchical permissions with inheritance 🎯 NEW
- ✅ Port Forwarding Control: Per-policy SSH forwarding permissions 🎯 NEW

**Recent Milestones:**
- v1.4: Recursive Groups & Enhanced Policies (January 2026) ✅ COMPLETED
- v1.3: RDP MP4 Conversion System (January 2026) ✅ COMPLETED
- v1.2-dev: RDP Session Viewer (January 2026) ✅ COMPLETED
- v1.1: Session History & Live View (January 2026) ✅ COMPLETED
- v1.0: Access Control V2 with Flexible Policies (December 2025)
- v0.9: Real-time Session Tracking with UTMP/WTMP (December 2025)

## Project Vision

Stworzenie kompletnego SSH/RDP jump hosta z:
- ✅ Uwierzytelnianiem per source IP (DONE)
- ✅ Czasowym przydzielaniem dostępów (DONE)
- ✅ Mapowaniem użytkowników per source IP (DONE - multiple IPs supported)
- ✅ Nagrywaniem sesji (DONE - SSH JSONL, RDP .pyrdp)
- ✅ Live view sesji (DONE - 2s polling for SSH)
- ⏳ Dynamicznym zarządzaniem pulą IP (PARTIAL - manual allocation)
- ⏳ Integracją z FreeIPA (TODO)

## Architecture Goal

```
Client 100.64.0.X
    ↓
    Connect to: 10.0.160.150:22 (SSH) or :3389 (RDP)
    ↓
Jump Host extracts:
    - Source IP: 100.64.0.X (identifies user)
    - Destination IP: 10.0.160.150 (identifies backend server)
    ↓
Access Control V2:
    - User from source IP has policy grant to backend?
    - Policy scope: group/server/service level?
    - Policy still valid (temporal)?
    - Protocol allowed (ssh/rdp/both)?
    - SSH login allowed (if SSH)?
    ↓
Proxy forwards to backend:
    - SSH: 10.30.0.200:22
    - RDP: 10.30.0.140:3389
    ↓
Session recorded to disk (JSONL for SSH, .pyrdp for RDP)
Session tracked in database (real-time monitoring)
Live view available in web GUI
```

---

## ✅ COMPLETED: v1.1 - Session Monitoring & Live View (January 2026)

### 🎯 Major Features Delivered

#### 1. Session History & Live View System
- **Session List**: `/sessions/` with filtering by protocol, status, user, server
- **Session Detail**: Full metadata display with 14 fields
- **Live SSH Viewer**: Real-time log streaming with 2-second polling
- **Terminal UI**: Dark theme with color-coded events, search, client/server filters
- **Recording Format**: JSONL (JSON Lines) for streaming writes
- **Performance**: LRU cache (maxsize=100) for session parser optimization
- **Download**: Support for SSH .log and RDP .pyrdp files

#### 2. Dashboard Auto-Refresh
- **Active Sessions Table**: Auto-updates every 5 seconds via AJAX
- **Statistics Cards**: Today's connections, denied, success rate
- **API Endpoints**: `/api/stats`, `/api/active-sessions`
- **Recent Sessions Widget**: Shows last 10 closed sessions with Started/Duration/Ended
- **Tooltips**: European date format (dd-mm-yyyy hh:mm:ss) on all "ago" timestamps

#### 3. Systemd Service Integration
- **jumphost-flask.service**: Flask web app (port 5000, user: p.mojski)
- **jumphost-ssh-proxy.service**: SSH proxy (port 22, user: root)
- **jumphost-rdp-proxy.service**: PyRDP MITM direct (port 3389, user: root)
- **Centralized Logs**: `/var/log/jumphost/{flask,ssh_proxy,rdp_mitm}.log`
- **Logrotate**: Daily rotation, 14-30 days retention
- **Auto-Restart**: All services configured with `Restart=always`

#### 4. Architecture Simplification
- **RDP**: Direct PyRDP MITM on 0.0.0.0:3389 (removed rdp_guard.py, rdp_wrapper.sh)
- **Logs**: Unified structure in /var/log/jumphost/
- **Service Management**: Full systemd integration with enable/disable/restart

#### 5. Live Recording System
- **SSH**: JSONL format - writes each event immediately to disk
- **Performance**: File opened in append mode, flushed after each write
- **Compatibility**: Parser handles both JSONL (streaming) and old JSON format
- **Live View**: Browser polls `/sessions/<id>/live?after=<timestamp>` every 2s
- **Cache Invalidation**: LRU cache uses (file_path, mtime) as key

### 📁 New Files Created
- `/opt/jumphost/src/web/blueprints/sessions.py` - Session history & live view blueprint
- `/opt/jumphost/src/web/templates/sessions/index.html` - Session list with filters
- `/opt/jumphost/src/web/templates/sessions/view.html` - Session detail + live viewer
- `/etc/systemd/system/jumphost-flask.service` - Flask systemd service
- `/etc/systemd/system/jumphost-ssh-proxy.service` - SSH proxy systemd service
- `/etc/systemd/system/jumphost-rdp-proxy.service` - RDP proxy systemd service
- `/etc/logrotate.d/jumphost` - Log rotation configuration

### 🗑️ Deprecated/Removed
- `src/proxy/rdp_guard.py` - No longer used (direct PyRDP MITM now)
- `src/proxy/rdp_wrapper.sh` - No longer used
- `src/proxy/rdp_proxy.py` - Deprecated Python wrapper

### 📊 Testing Results
- **Dashboard Refresh**: ✅ 5-second auto-update working
- **Live SSH View**: ✅ 2-second polling with new events
- **Session History**: ✅ Filtering by protocol/status/user/server
- **Recording Download**: ✅ SSH .log and RDP .pyrdp files
- **Systemd Services**: ✅ All 3 services running with auto-restart
- **Performance**: ✅ LRU cache eliminates repeated parsing

### 🐛 Issues Fixed
- Fixed API endpoint returning dict instead of Session objects
- Fixed dashboard auto-refresh selector (added #activeSessionsBody ID)
- Fixed Recent Sessions missing "Started" column
- Added tooltips with dd-mm-yyyy format to all timestamps
- Fixed JSONL recording to write immediately (not at session end)
- Fixed Flask becoming slow (added caching)

---

## ✅ COMPLETED: v1.3 - RDP MP4 Conversion System (January 2026)

### 🎯 Goal: Web-based RDP Session Video Playback

**Challenge Solved**: RDP recordings (.pyrdp files) required desktop Qt player. Implemented web-based MP4 conversion with background workers.

### ✅ Delivered Features

#### 1. Background Worker Queue System
- **Workers**: 2 systemd services (`jumphost-mp4-converter@1.service`, `@2.service`)
- **Queue**: SQLite `mp4_conversion_queue` table with status tracking
- **Concurrency**: Maximum 2 simultaneous conversions, 10 pending jobs
- **Polling**: Workers check database every 5 seconds
- **Priority**: "Rush" button to move jobs to front of queue
- **Resource Limits**: 150% CPU, 2GB RAM per worker
- **Logs**: `/var/log/jumphost/mp4-converter-worker{1,2}.log`
- **Auto-restart**: Systemd restarts on failure

#### 2. PyRDP MP4 Conversion
- **Environment**: Separate venv at `/opt/jumphost/venv-pyrdp-converter/`
- **Dependencies**: PySide6 + av + pyrdp-mitm
- **FPS**: 10 frames per second (quality/speed balance)
- **Storage**: `/var/log/jumphost/rdp_recordings/mp4_cache/`
- **Format**: H.264 MP4 with audio support
- **Performance**: ~15s for 1.8MB file, ~40s for 3.5MB file
- **Patches Applied**:
  - RDP version enum: Added `RDP10_12 = 0x80011` support
  - Python 3.13 fix: `BinaryIO` import in FileMapping.py
  - FPS override: Modified `convert/utils.py` to pass fps=10

#### 3. Progress Tracking & ETA
- **Real-time Updates**: Parses pyrdp-convert output via regex
- **Progress Bar**: Shows X of Y frames with percentage
- **ETA Calculation**: Based on elapsed time and frames processed
- **Queue Position**: Shows position for pending jobs
- **Status Badge**: Updates color (secondary/warning/primary/success/danger)
- **Polling Interval**: Frontend checks every 2 seconds

#### 4. Web UI Components
- **Convert Button**: Queues new conversion job (max 10 pending)
- **Progress Display**: Live progress bar with ETA countdown
- **Video Player**: HTML5 `<video>` with controls
- **Download Button**: Direct MP4 download link
- **Delete Button**: Remove MP4 from cache (known permission issue)
- **Priority Button**: Move job to front of queue
- **Retry Button**: Requeue failed conversions
- **4 Status Sections**: not-converted, converting, failed, completed

#### 5. API Endpoints
- `POST /sessions/<id>/convert` - Queue conversion (returns position)
- `GET /sessions/<id>/convert-status` - Get status/progress/eta
- `POST /sessions/<id>/convert/priority` - Move to front of queue
- `GET /sessions/<id>/mp4/stream` - Stream MP4 with range support
- `DELETE /sessions/<id>/mp4` - Delete MP4 cache file

#### 6. Database Schema
```sql
CREATE TABLE mp4_conversion_queue (
    id INTEGER PRIMARY KEY,
    session_id VARCHAR(255) UNIQUE NOT NULL,
    status VARCHAR(20) DEFAULT 'pending',  -- pending/converting/completed/failed
    progress INTEGER DEFAULT 0,
    total INTEGER DEFAULT 0,
    eta_seconds INTEGER,
    priority INTEGER DEFAULT 0,
    mp4_path TEXT,
    error_msg TEXT,
    created_at TIMESTAMP,
    started_at TIMESTAMP,
    completed_at TIMESTAMP
);
CREATE INDEX idx_status ON mp4_conversion_queue(status);
CREATE INDEX idx_priority ON mp4_conversion_queue(priority);
CREATE INDEX idx_created_at ON mp4_conversion_queue(created_at);
```

### 📁 New Files Created
- `/opt/jumphost/src/core/mp4_converter.py` - Worker process with queue management
- `/opt/jumphost/venv-pyrdp-converter/` - Separate Python environment with PySide6
- `/etc/systemd/system/jumphost-mp4-converter@.service` - Systemd template
- `/var/log/jumphost/rdp_recordings/mp4_cache/` - MP4 output directory
- Database migration: Added `mp4_conversion_queue` table

### 🔧 Modified Files
- `src/core/database.py` - Added `MP4ConversionQueue` model
- `src/web/blueprints/sessions.py` - Added 5 MP4 endpoints
- `src/web/templates/sessions/view.html` - Added conversion UI
- `src/web/static/js/custom.js` - Disabled global alert auto-hide
- `venv-pyrdp-converter/lib/python3.13/site-packages/pyrdp/enum/rdp.py` - RDP version fix
- `venv-pyrdp-converter/lib/python3.13/site-packages/pyrdp/convert/utils.py` - FPS=10

### 📊 Testing Results
- **Small file** (1.8MB .pyrdp): ~15s conversion → 180KB MP4 ✅
- **Medium file** (3.5MB .pyrdp): ~40s conversion → 725KB MP4 ✅
- **Progress tracking**: Real-time updates with accurate ETA ✅
- **Video streaming**: HTML5 player with seek support ✅
- **Queue system**: FIFO + priority working correctly ✅
- **Priority rush**: Moves job to front immediately ✅
- **Concurrent workers**: Both workers process jobs simultaneously ✅
- **Video playback**: `video.load()` fix enables immediate playback ✅

### 🐛 Critical Bugs Fixed
1. **Global Alert Auto-hide**: `custom.js` was hiding all `.alert` elements after 5s
   - Impact: Content disappeared on sessions, users, groups pages
   - Fix: Commented out entire auto-hide block
   - Result: All alerts stay visible unless manually closed

2. **Video Not Playing**: Video player loaded but didn't start playback
   - Root cause: Browser didn't load source when section became visible
   - Fix: Added `video.load()` call when status='completed'
   - Result: Video plays immediately after conversion

3. **Wrong Video URL**: Relative path `/sessions/<id>/mp4/stream` failed
   - Fix: Changed to `url_for('sessions.stream_mp4', session_id=...)`
   - Result: Proper absolute URL generation

### ⚠️ Known Issues
- **Delete MP4 Permission**: Flask runs as p.mojski, workers as root
  - Files owned by root, Flask can't delete
  - Workaround: Admin manual cleanup or chown mp4_cache/ to p.mojski
- **datetime.utcnow() Warnings**: 3 deprecation warnings in Python 3.13
  - Non-critical, functionality works correctly
  - TODO: Replace with `datetime.now(datetime.UTC)`

### 💡 Design Decisions
- **FPS=10**: Balance between quality and speed (3x faster than realtime)
- **2 Workers**: Optimal for VM resources, prevents overload
- **10 Pending Max**: Reasonable queue size, prevents spam
- **2s Polling**: Fast enough for live feel, not too aggressive
- **Separate venv**: Isolates PySide6 dependencies from main app
- **File Glob**: pyrdp-convert adds prefix to filename, use pattern matching

---

---

## � IN PROGRESS: v1.4 - Advanced Access Control & User Experience (January 2026)

### 🎯 Goals: Recursive Groups, Port Forwarding, Curl CLI

**Status**: Planning phase - January 2026

**Strategy**: Build from foundation to interface
1. Recursive groups (infrastructure)
2. Port forwarding (features using new permissions)
3. Curl API (user-friendly interface)

---

### 📋 Feature 1: Recursive Groups & Nested Permissions

**Priority**: 🔴 Critical - Foundation for all access control

**Problem**: Current system supports flat groups only. Need hierarchical organization.

**Requirements**:
- **User Groups**: Users can belong to groups (e.g., "biuro", "ideo")
- **Group Nesting**: Groups can contain other groups (e.g., "biuro" ⊂ "ideo")
- **Permission Inheritance**: User in "biuro" automatically gets "ideo" permissions
- **Server Groups**: Same nesting for servers (e.g., "prod-web" ⊂ "production")
- **Cycle Detection**: Prevent infinite loops (A → B → C → A)

**Use Cases**:
```
Example 1: User Groups
- Group "ideo" (parent)
  └── Group "biuro" (child)
      └── User "p.mojski"
      
Grant for "ideo" → applies to "biuro" → applies to "p.mojski"

Example 2: Server Groups
- Group "production" (parent)
  ├── Group "prod-web" (child)
  │   ├── web01.prod
  │   └── web02.prod
  └── Group "prod-db" (child)
      ├── db01.prod
      └── db02.prod
      
Grant to "production" → access to all 4 servers
```

**Database Changes**:
```sql
-- New Tables
CREATE TABLE user_groups (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) UNIQUE NOT NULL,
    description TEXT,
    parent_group_id INTEGER REFERENCES user_groups(id),  -- Recursive!
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE user_group_members (
    id SERIAL PRIMARY KEY,
    user_group_id INTEGER REFERENCES user_groups(id),
    user_id INTEGER REFERENCES users(id),
    added_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(user_group_id, user_id)
);

-- Extend Existing
ALTER TABLE server_groups ADD COLUMN parent_group_id INTEGER REFERENCES server_groups(id);
ALTER TABLE access_policies ADD COLUMN user_group_id INTEGER REFERENCES user_groups(id);
```

**Algorithm: Recursive Membership Resolution**:
```python
def get_all_user_groups(user_id, db):
    """Get all groups user belongs to (direct + inherited via parent groups)"""
    visited = set()
    queue = get_direct_groups(user_id)  # Start with direct membership
    
    while queue:
        group = queue.pop(0)
        if group.id in visited:
            continue  # Cycle detection
        visited.add(group.id)
        
        # Add parent groups to queue
        if group.parent_group_id:
            parent = db.query(UserGroup).get(group.parent_group_id)
            if parent:
                queue.append(parent)
    
    return visited

def get_all_servers_in_group(group_id, db):
    """Get all servers in group (direct + inherited from child groups)"""
    visited = set()
    queue = [group_id]
    
    while queue:
        gid = queue.pop(0)
        if gid in visited:
            continue
        visited.add(gid)
        
        # Add direct servers
        servers = get_direct_servers(gid)
        visited.update(servers)
        
        # Add child groups to queue
        children = db.query(ServerGroup).filter(ServerGroup.parent_group_id == gid).all()
        queue.extend([c.id for c in children])
    
    return visited
```

**Access Control Integration**:
```python
# In AccessControlEngineV2.check_access_v2()
def check_access_v2(self, db, source_ip, dest_ip, protocol):
    user = self.find_user_by_source_ip(db, source_ip)
    server = self.find_backend_by_proxy_ip(db, dest_ip)
    
    # Get ALL groups user belongs to (including inherited)
    user_groups = get_all_user_groups(user.id, db)
    
    # Check policies for:
    # 1. Direct user access
    # 2. Any of user's groups (direct or inherited)
    policies = db.query(AccessPolicy).filter(
        or_(
            AccessPolicy.user_id == user.id,
            AccessPolicy.user_group_id.in_(user_groups)
        ),
        # ... rest of policy checks
    ).all()
```

**Cycle Detection**:
```python
def validate_no_cycles(group_id, new_parent_id, db):
    """Ensure setting parent_id won't create cycle"""
    visited = set([group_id])
    current = new_parent_id
    
    while current:
        if current in visited:
            raise ValueError(f"Cycle detected: {group_id} -> ... -> {current} -> {group_id}")
        visited.add(current)
        
        parent_group = db.query(UserGroup).get(current)
        current = parent_group.parent_group_id if parent_group else None
```

**Web GUI Changes**:
- User Groups management page (create, nest, assign users)
- Server Groups tree view (drag & drop nesting)
- Policy wizard: Select user OR user group
- Visualization: Group hierarchy tree

**Performance Considerations**:
- Cache group membership in Redis (TTL 5min)
- Indexed queries on parent_group_id
- Limit nesting depth (max 10 levels)

**Migration Path**:
1. Create new tables (Alembic migration)
2. Migrate existing server_groups (all at root level initially)
3. Deploy new AccessControlEngineV2
4. Test with simple 2-level hierarchy
5. Roll out to production

**Status**: 
- [ ] Database schema design
- [ ] Alembic migration
- [ ] Recursive algorithms (membership, cycle detection)
- [ ] Update AccessControlEngineV2
- [ ] Web GUI for group management
- [ ] Testing (edge cases, cycles, performance)

---

### 📋 Feature 2: SSH Port Forwarding (-L / -R)

**Priority**: 🟡 High - Critical for daily productivity

**Problem**: Current SSH proxy doesn't support port forwarding. Users can't use VS Code Remote SSH, database tunnels, or other port forwarding workflows.

**Requirements**:
- **Local Forwarding** (`ssh -L`): Client opens port, forwards to backend
- **Remote Forwarding** (`ssh -R`): Backend opens port, forwards to client
- **Access Control**: New permission `port_forwarding_allowed` (per user or group)
- **Logging**: Track all port forward requests (source, dest, ports)
- **Restrictions**: Configurable allowed destination IPs/ports

**Use Cases**:
```bash
# Local forwarding (ssh -L)
ssh -L 5432:db-backend:5432 jumphost
# Now: localhost:5432 -> jumphost -> db-backend:5432

# Remote forwarding (ssh -R)
ssh -R 8080:localhost:3000 jumphost
# Now: jumphost:8080 -> your-machine:3000

# VS Code Remote SSH
# VS Code opens random high port, forwards stdin/stdout
```

**Paramiko Channels**:
- `direct-tcpip`: Local forwarding (ssh -L)
- `forwarded-tcpip`: Remote forwarding (ssh -R)

**Database Changes**:
```sql
ALTER TABLE users ADD COLUMN port_forwarding_allowed BOOLEAN DEFAULT FALSE;
ALTER TABLE user_groups ADD COLUMN port_forwarding_allowed BOOLEAN DEFAULT FALSE;

CREATE TABLE port_forward_sessions (
    id SERIAL PRIMARY KEY,
    session_id VARCHAR(255) REFERENCES sessions(session_id),
    source_ip VARCHAR(45),
    username VARCHAR(255),
    forward_type VARCHAR(20),  -- 'local' or 'remote'
    listen_host VARCHAR(255),
    listen_port INTEGER,
    dest_host VARCHAR(255),
    dest_port INTEGER,
    started_at TIMESTAMP DEFAULT NOW(),
    ended_at TIMESTAMP,
    bytes_sent BIGINT DEFAULT 0,
    bytes_received BIGINT DEFAULT 0
);
```

**SSH Proxy Changes** (`src/proxy/ssh_proxy.py`):
```python
class SSHProxyServerInterface(paramiko.ServerInterface):
    def check_channel_request(self, kind, chanid):
        if kind == 'session':
            return paramiko.OPEN_SUCCEEDED
        elif kind == 'direct-tcpip':  # ssh -L
            return self._check_port_forward_request('local')
        elif kind == 'forwarded-tcpip':  # ssh -R
            return self._check_port_forward_request('remote')
        return paramiko.OPEN_FAILED_ADMINISTRATIVELY_PROHIBITED
    
    def _check_port_forward_request(self, forward_type):
        # Check if user has port_forwarding_allowed
        if not self.user.port_forwarding_allowed:
            # Check group permissions (recursive!)
            user_groups = get_all_user_groups(self.user.id, db)
            if not any(g.port_forwarding_allowed for g in user_groups):
                logger.warning(f"Port forwarding denied for {self.username}")
                return paramiko.OPEN_FAILED_ADMINISTRATIVELY_PROHIBITED
        
        logger.info(f"Port forwarding {forward_type} allowed for {self.username}")
        return paramiko.OPEN_SUCCEEDED
    
    def check_channel_direct_tcpip_request(self, chanid, origin, destination):
        """Called for ssh -L"""
        dest_addr, dest_port = destination
        
        # Validate destination (optional whitelist)
        if not self._validate_port_forward_destination(dest_addr, dest_port):
            return paramiko.OPEN_FAILED_ADMINISTRATIVELY_PROHIBITED
        
        # Log port forward session
        self._log_port_forward('local', origin, destination)
        
        return paramiko.OPEN_SUCCEEDED
```

**Port Forward Handler**:
```python
def handle_direct_tcpip(channel, origin, destination):
    """Forward traffic between client and destination"""
    try:
        dest_addr, dest_port = destination
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect((dest_addr, dest_port))
        
        # Bidirectional forwarding
        while True:
            r, w, x = select.select([channel, sock], [], [])
            if channel in r:
                data = channel.recv(4096)
                if not data:
                    break
                sock.sendall(data)
            if sock in r:
                data = sock.recv(4096)
                if not data:
                    break
                channel.sendall(data)
    finally:
        sock.close()
        channel.close()
```

**Configuration**:
```python
# In config or database
PORT_FORWARD_WHITELIST = {
    'allowed_dest_ips': ['10.30.0.*', '192.168.*'],  # Glob patterns
    'blocked_ports': [22, 3389],  # No forwarding to SSH/RDP ports
    'require_approval': False  # Future: admin approval workflow
}
```

**Web GUI**:
- User profile: Checkbox "Allow Port Forwarding"
- Group settings: Checkbox "Allow Port Forwarding" (inherited by members)
- Active Port Forwards widget (dashboard)
- Audit log: Port forward attempts (granted/denied)

**Status**:
- [ ] Database schema (port_forwarding_allowed, port_forward_sessions)
- [ ] SSH proxy: channel request handlers
- [ ] Bidirectional traffic forwarding
- [ ] Logging and audit
- [ ] Web GUI toggles
- [ ] Testing (ssh -L, ssh -R, VS Code Remote)

---

### 📋 Feature 3: Curl-based CLI API

**Priority**: 🟢 Medium - User experience enhancement

**Problem**: Users need to interact with jumphost from any machine without installing tools. Only `curl` is universally available.

**Requirements**:
- **User-Agent Detection**: Recognize curl, return plain text instead of HTML
- **Simple Endpoints**: Short, memorable URLs
- **Self-Service**: Request access, check status, list grants
- **Admin Approval**: Workflow for sensitive operations
- **No Auth (for reads)**: Use source IP (already authenticated)

**Example Usage**:
```bash
# Check who you are
$ curl jump/whoami
You are: p.mojski (pawel.mojski@example.com)
Source IP: 100.64.0.20
Active grants: 3 servers (5 expire in < 7 days)

# Backend info
$ curl jump/i/10.30.0.140
test-rdp-server (10.30.0.140)
  Proxy IP: 10.0.160.130
  Groups: test-servers, rdp-hosts
  Your access: ✓ RDP (expires 2026-02-01)

# List your grants
$ curl jump/p/list
Active Grants:
  [RDP] 10.30.0.140 (test-rdp-server) - expires 2026-02-01
  [SSH] 10.30.0.200 (linux-dev)       - expires 2026-01-15
  [SSH] 10.30.0.201 (linux-prod)      - permanent

# Request new access
$ curl jump/p/request/ssh/10.30.0.202
Access request created: #42
Server: linux-staging (10.30.0.202)
Protocol: SSH
Status: Pending admin approval
View: http://jump:5000/requests/42

# Add your IP (if multiple IPs)
$ curl -X POST jump/p/add-ip/100.64.0.99
Request created: #43
New IP: 100.64.0.99 will be linked to your account
Status: Pending admin approval
```

**API Endpoints**:
```python
# src/web/blueprints/cli_api.py

@cli_api.route('/whoami')
def whoami():
    source_ip = request.remote_addr
    user = find_user_by_source_ip(source_ip)
    
    if is_curl_request():
        return format_plain_text({
            'user': user.username,
            'email': user.email,
            'source_ip': source_ip,
            'grants': count_active_grants(user)
        })
    else:
        return jsonify({...})  # JSON for browsers

@cli_api.route('/i/<path:ip_or_name>')
def backend_info(ip_or_name):
    server = find_server(ip_or_name)  # By IP or name
    user = find_user_by_source_ip(request.remote_addr)
    
    access = check_access(user, server)
    
    return format_plain_text({
        'server': server,
        'proxy_ip': server.proxy_ip,
        'groups': server.groups,
        'your_access': access
    })

@cli_api.route('/p/request/<protocol>/<ip>')
def request_access(protocol, ip):
    user = find_user_by_source_ip(request.remote_addr)
    server = find_server(ip)
    
    # Create access request (new table)
    req = AccessRequest(
        user_id=user.id,
        server_id=server.id,
        protocol=protocol,
        status='pending',
        requested_at=datetime.now()
    )
    db.add(req)
    db.commit()
    
    # Notify admins (future: email/Slack)
    
    return format_plain_text({
        'request_id': req.id,
        'status': 'pending',
        'url': f'http://{request.host}/requests/{req.id}'
    })
```

**User-Agent Detection**:
```python
def is_curl_request():
    ua = request.headers.get('User-Agent', '').lower()
    return 'curl' in ua or 'wget' in ua
```

**Admin Approval Workflow**:
```sql
CREATE TABLE access_requests (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),
    server_id INTEGER REFERENCES servers(id),
    protocol VARCHAR(10),
    justification TEXT,
    status VARCHAR(20) DEFAULT 'pending',  -- pending/approved/denied
    requested_at TIMESTAMP DEFAULT NOW(),
    reviewed_by INTEGER REFERENCES users(id),
    reviewed_at TIMESTAMP,
    approval_notes TEXT
);
```

**Web GUI**:
- `/requests` - Pending requests list (admins only)
- Approve/Deny buttons
- Auto-create AccessPolicy on approval

**Shortcuts**:
```bash
# Add to /etc/hosts or DNS
10.0.160.5  jump

# Or create shell alias
alias jh='curl -s jump'
jh /whoami
jh /i/10.30.0.140
```

**Status**:
- [ ] Blueprint: cli_api.py
- [ ] User-agent detection
- [ ] Plain text formatters
- [ ] Endpoints: whoami, info, list, request
- [ ] Database: access_requests table
- [ ] Admin approval GUI
- [ ] Testing with curl
- [ ] Documentation (user guide)

---

## 📋 Backlog: Future Enhancements

### MP4 System Improvements
- [ ] Fix delete MP4 permission issue (chown mp4_cache to p.mojski)
- [ ] Replace datetime.utcnow() with datetime.now(datetime.UTC) (Python 3.13)
- [ ] Configurable FPS per conversion (ENV variable or UI setting)
- [ ] Auto-cleanup old MP4 files (retention policy)
- [ ] WebSocket/SSE for real-time progress (reduce polling)
- [ ] Conversion metrics dashboard (avg time, success rate)

### Session Monitoring
- [ ] SSH session video recording (ttyrec/asciinema format)
- [ ] Session playback speed controls (0.5x, 1x, 2x)
- [ ] Search within session transcripts
- [ ] Export session reports (PDF/JSON)

### Advanced Access Control
- [ ] FreeIPA integration (user sync + authentication)
- [ ] Multi-factor authentication (TOTP)
- [ ] Time-based access (only during business hours)
- [ ] Break-glass emergency access

### Performance & Scaling
- [ ] Redis cache for session state
- [ ] Connection pooling for database
- [ ] Load balancing across multiple jump hosts
- [ ] Separate SSH proxy instances per backend

### Monitoring & Alerting
- [ ] Prometheus metrics export
- [ ] Grafana dashboards
- [ ] Email/Slack alerts for denied access
- [ ] Long session warnings
- [ ] Resource usage monitoring

---

## 🗑️ DEPRECATED: v1.2 - RDP Session Viewer (Completed as v1.3)

This section moved to v1.3 - RDP MP4 Conversion System.

**Original Goal**: Web-based RDP session replay  
**Status**: ✅ COMPLETED in v1.3 with full MP4 conversion pipeline

### Historical Notes (v1.2-dev)
- RDP Recording Metadata Extraction ✅
- Web Interface - Basic Info Display ✅
- JSON conversion with caching ✅
- MP4 conversion blocked by CPU (resolved in v1.3) ✅

---

## 🔄 OLD CONTEXT: v1.2 - RDP Session Viewer (January 2026) - COMPLETED, MOVED TO v1.3

### 🎯 Goal: Web-based RDP Session Replay

**Challenge**: RDP recordings (.pyrdp files) require desktop Qt player for full video replay. Need web-based solution for security audit.

**Current Status**: Backend infrastructure complete, waiting for VM CPU upgrade for MP4 conversion.

### ✅ Completed Work

#### 1. RDP Recording Metadata Extraction
- **JSON Conversion**: `pyrdp-convert -f json` integration
- **Caching System**: `/var/log/jumphost/rdp_recordings/json_cache/`
- **Metadata Parsing**: Host, resolution, username, domain, duration
- **Event Counting**: Keyboard keystrokes, mouse events
- **Function**: `get_rdp_recording_info()` in sessions.py

#### 2. Web Interface - Basic Info Display
- **Session Summary Card**: Host, resolution, duration, event statistics
- **Download Support**: .pyrdp file download button
- **Playback Instructions**: How to use pyrdp-player locally
- **Fallback UI**: If JSON conversion fails, show basic file info
- **Template**: Updated `templates/sessions/view.html`

#### 3. API Endpoints
- **Route**: `/sessions/<id>/rdp-events` - Returns converted JSON
- **Validation**: Checks protocol is RDP, session exists, recording available
- **Error Handling**: 404/500 with error messages

### ⏸️ Blocked: MP4 Video Conversion

**Issue**: PyRDP MP4 export requires:
- PySide6 (Qt for Python)
- CPU instructions: ssse3, sse4.1, sse4.2, popcnt
- Current VM CPU: "Common KVM processor" (basic, missing required flags)

**Solution Path**:
1. ✅ Created separate venv: `/opt/jumphost/venv-pyrdp-converter/`
2. ✅ Installed: PySide6 + av + pyrdp-mitm
3. ❌ **BLOCKED**: CPU doesn't support SSSE3/SSE4 (Qt requirement)
4. 🔜 **NEXT**: Proxmox VM CPU upgrade to `host` type

**Proxmox Configuration Needed**:
```bash
# VM Configuration (GUI or /etc/pve/qemu-server/XXX.conf):
cpu: host
# OR specific flags:
cpu: kvm64,flags=+ssse3;+sse4.1;+sse4.2;+popcnt
```

### 📋 After CPU Upgrade - TODO

1. **Test MP4 Conversion**:
   ```bash
   source /opt/jumphost/venv-pyrdp-converter/bin/activate
   pyrdp-convert -f mp4 -o /tmp/test.mp4 /var/log/jumphost/rdp_recordings/replays/recording.pyrdp
   ```

2. **Implement MP4 Generation**:
   - Background job queue (Celery or simple subprocess)
   - Convert .pyrdp → .mp4 on-demand or scheduled
   - Cache MP4 files in `/var/log/jumphost/rdp_recordings/mp4_cache/`
   - Progress tracking for long conversions

3. **Web Video Player**:
   - HTML5 `<video>` element in session detail page
   - Timeline scrubbing, play/pause controls
   - Keyboard shortcuts (space, arrows)
   - Optional: Download MP4 button

4. **Performance Optimization**:
   - Async conversion (don't block Flask)
   - Queue system for multiple conversions
   - Thumbnail generation for quick preview
   - Bandwidth throttling for large videos

### 🗂️ Files Modified (v1.2-dev)

**Backend**:
- `src/web/blueprints/sessions.py`:
  - Added `get_rdp_recording_info()` - JSON conversion with caching
  - Added `format_duration()` - Human-readable time formatting
  - Added `/sessions/<id>/rdp-events` endpoint
  - Glob pattern matching for pyrdp-convert output filenames

**Frontend**:
- `templates/sessions/view.html`:
  - RDP session summary card (metadata + statistics)
  - Download + playback instructions
  - Placeholder for future video player
  - Graceful fallback if conversion fails

**System**:
- Created `/var/log/jumphost/rdp_recordings/json_cache/` (owned by p.mojski)
- Created `/opt/jumphost/venv-pyrdp-converter/` venv (PySide6 ready)

### 📊 Test Results

**JSON Conversion**:
- ✅ Manual test: 254 events converted in <1s
- ✅ Metadata extraction: host, resolution, username, timestamps
- ✅ Event counting: keyboard (78), mouse (175) for test session
- ✅ Cache system: Checks mtime, avoids re-conversion

**Web Interface**:
- ✅ Session detail shows RDP metadata
- ✅ Download button works
- ✅ Instructions displayed correctly
- ❌ MP4 video player: Blocked by CPU (PySide6 segfault)

### 🐛 Issues Fixed

- Fixed pyrdp-convert output filename pattern (appends source name)
- Fixed JSON cache directory permissions (p.mojski ownership)
- Fixed glob pattern matching for cached JSON files
- Removed non-functional event timeline (replaced with summary)

### 🎯 Success Criteria (After CPU Upgrade)

- [ ] MP4 conversion works without errors
- [ ] Web interface displays embedded video player
- [ ] Video playback smooth (no buffering on 1920x1200)
- [ ] Conversion time acceptable (<30s for 5-minute session)
- [ ] Audit team can review RDP sessions without downloading files

---

## Phase 1: Core Infrastructure ✓ COMPLETE

### Task 1: Environment Setup ✓
- [x] Debian 13 installation
- [x] Python 3.13 + virtualenv
- [x] PostgreSQL setup
- [x] Disk expansion (3GB → 35GB)

### Task 2: Database Schema ✓ + V2 UPGRADE ⭐
- [x] Users table with source_ip (V1)
- [x] Servers table (V1)
- [x] Access grants with temporal fields (V1 - legacy)
- [x] IP allocations table (V1)
- [x] Session recordings table (V1)
- [x] Audit logs table (V1)
- [x] SQLAlchemy ORM models (V1)
- [x] **NEW V2**: user_source_ips (multiple IPs per user)
- [x] **NEW V2**: server_groups (tags/groups)
- [x] **NEW V2**: server_group_members (N:M relationship)
- [x] **NEW V2**: access_policies (flexible granular control)
- [x] **NEW V2**: policy_ssh_logins (SSH login restrictions)
- [x] **NEW V2**: Alembic migration (8419b886bc6d)
- 📄 **Documentation**: `/opt/jumphost/FLEXIBLE_ACCESS_CONTROL_V2.md`

### Task 3: Access Control Engine ✓ + V2 UPGRADE ⭐
- [x] check_access() with source IP + username (V1 - legacy)
- [x] Temporal validation (start_time/end_time) (V1)
- [x] Backend server verification (V1)
- [x] Support for RDP (username=None, source IP only) (V1)
- [x] **NEW V2**: check_access_v2() with policy-based logic
- [x] **NEW V2**: Group-level, server-level, service-level scopes
- [x] **NEW V2**: Protocol filtering (ssh/rdp/all)
- [x] **NEW V2**: SSH login restrictions support
- [x] **NEW V2**: Multiple source IPs per user
- [x] **NEW V2**: Legacy fallback for backward compatibility
- 📂 **File**: `/opt/jumphost/src/core/access_control_v2.py`

### Task 4: IP Pool Manager ✓
- [x] Pool definition: 10.0.160.128/25
- [x] allocate_ip() function
- [x] release_ip() function
- [x] get_pool_status()
- [x] allocate_permanent_ip() for backend servers
- [ ] **TODO**: Integration with V2 policies (auto-allocate on grant)

---

## Phase 2: SSH Proxy ✓ COMPLETE + V2 PRODUCTION

### Status: 🟢 FULLY OPERATIONAL
- ✅ Listening on: `0.0.0.0:22`
- ✅ Access Control: AccessControlEngineV2
- ✅ Authentication: Transparent (agent forwarding + password fallback)
- ✅ Session Recording: `/var/log/jumphost/ssh/`
- ✅ Production Testing: 13/13 scenarios passed

### Key Implementation
**File**: `/opt/jumphost/src/proxy/ssh_proxy.py`

**Critical Fix**: SSH Login Forwarding
- Problem: Backend auth used database username (p.mojski) instead of client's SSH login (ideo)
- Solution: Store `ssh_login` in handler, use for backend authentication
- Code: `backend_transport.auth_password(server_handler.ssh_login, password)`

**Authentication Flow**:
1. Client connects with pubkey → Accept
2. Check for agent forwarding (`agent_channel`)
3. If available → Use forwarded agent for backend auth
4. If not available → Show helpful error message
5. Client can retry with password: `ssh -o PubkeyAuthentication=no user@host`

**Backup**: `/opt/jumphost/src/proxy/ssh_proxy.py.working_backup_20260104_113741`

---

## Phase 3: RDP Proxy ✓ COMPLETE + V2 PRODUCTION

### Status: 🟢 FULLY OPERATIONAL
- ✅ Listening on: `0.0.0.0:3389`
- ✅ Access Control: AccessControlEngineV2
- ✅ Session Recording: `/var/log/jumphost/rdp_recordings/`
- ✅ Production Testing: Validated 100.64.0.39 → 10.0.160.130 → 10.30.0.140

### Key Implementation
**File**: `/opt/jumphost/venv/lib/python3.13/site-packages/pyrdp/core/mitm.py`

**Critical Fix**: Destination IP Extraction
- Problem: When listening on `0.0.0.0`, cannot determine which backend to route to in `buildProtocol()`
- Root Cause: `buildProtocol()` called before socket established, only has source IP/port
- Solution: Wrap `connectionMade()` to extract dest_ip from socket after connection:
  ```python
  sock = protocol.transport.socket
  dest_ip = sock.getsockname()[0]  # e.g., 10.0.160.130
  ```
- Then find backend: `find_backend_by_proxy_ip(db, dest_ip)` → `10.30.0.140`
- Update state: `mitm.state.effectiveTargetHost = backend_server.ip_address`
- PyRDP's `connectToServer()` uses `state.effectiveTargetHost` to connect to backend

**Why This Works**:
1. Client connects to 10.0.160.130:3389
2. `buildProtocol()` creates MITM, wraps `connectionMade()`
3. `connectionMade()` extracts 10.0.160.130 from socket
4. Looks up backend: 10.0.160.130 → 10.30.0.140 (from ip_allocations table)
5. Checks access: 100.64.0.39 + 10.0.160.130 + rdp → Policy #8
6. Sets `state.effectiveTargetHost = "10.30.0.140"`
7. Original `connectionMade()` triggers `connectToServer()` which connects to 10.30.0.140:3389

**Integration Points**:
- Import: `from core.access_control_v2 import AccessControlEngineV2`
- Database: `from core.database import SessionLocal, IPAllocation, AuditLog`
- Access Check: `check_access_v2(db, source_ip, dest_ip, 'rdp')`
- Backend Lookup: `find_backend_by_proxy_ip(db, dest_ip)`

### Task 5: CLI Management Tool ✓ + V2 CLI ⭐
- [x] Typer + Rich tables (V1)
- [x] add-user command (V1)
- [x] add-server command (V1)
- [x] grant-access command with --duration (V1 - legacy)
- [x] list-users, list-servers, list-grants (V1)
- [x] **NEW V2 CLI**: jumphost_cli_v2.py (11 commands)
  - add-user-ip, list-user-ips, remove-user-ip
  - create-group, list-groups, show-group
  - add-to-group, remove-from-group
  - grant-policy (with full flexibility)
  - list-policies, revoke-policy
- 📂 **File**: `/opt/jumphost/src/cli/jumphost_cli_v2.py`
- 🧪 **Test**: `/opt/jumphost/test_access_v2.py` (Mariusz/Jasiek scenario)

---

## Phase 2: SSH Proxy ✓ COMPLETE

### Task 6: SSH Proxy Implementation ✓
- [x] Paramiko SSH server
- [x] Password authentication
- [x] Public key authentication
- [x] SSH agent forwarding (AgentServerProxy)
- [x] PTY forwarding with term/dimensions
- [x] Exec support (SCP)
- [x] Subsystem support (SFTP)
- [x] Session recording (JSON format)
- [x] Access control integration
- [x] Audit logging

**Status**: 100% WORKING - Production ready!

**Current Config**:
- Listen: 10.0.160.129:22
- Backend: 10.0.160.4:22 (hardcoded)

---

## Phase 3: RDP Proxy ✓ COMPLETE

### Task 7: PyRDP MITM Setup ✓
- [x] Install pyrdp-mitm
- [x] Fix Python 3.13 compatibility (typing.BinaryIO)
- [x] Apply RDP version patch (RDPVersion._missing_)
- [x] Test with Windows RDP client
- [x] Session recording to .pyrdp files

### Task 8: RDP Guard Proxy ✓
- [x] Async TCP proxy (Python asyncio)
- [x] Source IP-based access control
- [x] Backend server verification
- [x] Audit logging (access granted/denied)
- [x] Access denial with message
- [x] Forward to PyRDP MITM on localhost:13389

**Status**: 100% WORKING - Production ready!

**Current Config**:
- Guard: 10.0.160.129:3389 → PyRDP: localhost:13389 → Backend: 10.30.0.140:3389

---

## Phase 4: Architecture Refactor ✓ COMPLETE

### Task 9: Dynamic IP Pool-Based Routing ✓ COMPLETE
**Priority**: CRITICAL

**Goal**: Każdy backend dostaje swój dedykowany IP z puli, proxy nasłuchuje na 0.0.0.0 i routuje na podstawie destination IP

**Completed Changes**:

#### A. SSH Proxy Changes ✓
1. **✓ Moved management SSH to port 2222**
   ```bash
   # /etc/ssh/sshd_config
   Port 2222
   ListenAddress 10.0.160.5
   # Restarted: systemctl restart sshd
   ```

2. **✓ SSH Proxy listens on 0.0.0.0:22**
   ```python
   # src/proxy/ssh_proxy.py - już było poprawnie zaimplementowane
   server = paramiko.Transport(('0.0.0.0', 22))
   ```

3. **✓ Destination IP extraction in SSH handler**
   ```python
   def check_auth_password(self, username, password):
       source_ip = self.transport.getpeername()[0]
       # Extract destination IP
       dest_ip = self.transport.getsockname()[0]
       
       # Lookup backend by dest_ip from ip_allocations table
       backend_lookup = self.access_control.find_backend_by_proxy_ip(db, dest_ip)
       backend_server = b ✓
1. **✓ Listens on 0.0.0.0:3389**
   ```python
   # src/proxy/rdp_guard.py - już było poprawnie zaimplementowane
   guard = RDPGuardProxy(
       listen_host='0.0.0.0',
       listen_port=3389,
       pyrdp_host='127.0.0.1',
       pyrdp_port=13389
   )
   ```

2. **✓ Destination IP extraction from socket**
   ```python
   async def handle_client(self, reader, writer):
       source_ip = writer.get_extra_info('peername')[0]
       # Extract destination IP
       sock = writer.get_extra_info('socket')
       dest_ip = sock.getsockname()[0]
       
       # Lookup backend by dest_ip from ip_allocations table
       backend_lookup = self.access_control.find_backend_by_proxy_ip(db, dest_ip)
       backend_server = backend_lookup['server']
       
       # Lookup backend by dest_ip
       backend_server = find_backend_by_proxy_ip(db, dest_ip)
   ```Schema Changes ✓
**✓ Zmieniono strategię**: Zamiast kolumny `proxy_ip` w `servers`, użyto istniejącej tabeli `ip_allocations` z:
- `server_id` - link do serwera
- `allocated_ip` - IP z puli przydzielony do serwera (UNIQUE)
- `user_id` - NULL dla permanent server allocations
- `source_ip` - NULL dla permanent server allocations  
- `expires_at` - NULL dla permanent allocations (nigdy nie wygasa)

**✓ Schema fixes**:
```sql
-- Usunięto NOT NULL constraints żeby umożliwić permanent allocations
ALTER TABLE ip_allocations ALTER COLUMN user_id DROP NOT NULL;
ALTER TABLE ip_allocations ALTER COLUMN source_ip DROP NOT NULL;
ALTER TABLE ip_allocations ALTER COLUMN expires_at DROP NOT NULL;
```

**✓ Workflow Implementation**:
1. **✓** Admin dodaje server: `add-server Test-SSH-Server 10.0.160.4 linux`
2. **✓** Admin przydziela IP z puli: `assign-proxy-ip 1 10.0.160.129`
3. **✓** System zapisujmplementation ✓
**✓ Implemented Functions**:
```python
# src/core/ip_pool.py
def allocate_permanent_ip(db, server_id, specific_ip=None):
    """Allocate permanent IP from pool for server (never expires)"""
    # Creates IPAllocation with user_id=NULL, expires_at=NULL
    # Allocates specific IP or next available from pool
    
def release_ip(db, allocated_ip):
    """Release IP back to pool and remove from interface"""
    # Marks as released_at=now
    # Removes IP from network interface
```

**✓ CLI Commands Implemented**:
```bash
# Assign IP from pool to server
jumphost_cli.py assign-proxy-ip <server_id> [specific_ip]

# Remove IP allocation from server
jumphost_cli.py remove-proxy-ip <server_id>

# List all allocations (permanent and temporary)
jumphost_cli.py list-allocations
```

**✓ Testing Completed**:
1. **✓** Added 2 servers: Test-SSH-Server (ID:1), Windows-RDP-Server (ID:2)
2. **✓** Assigned IPs: 10.0.160.129→Server 1, 10.0.160.130→Server 2  
3. **✓** IPs configured on interface ens18
4. **✓** Created users: p.mojski, p.mojski.win
5. **✓** Created grants: p.mojski→SSH Server, p.mojski.win→RDP Server (480 min)
6. **✓** SSH Proxy running on 0.0.0.0:22, routing works
7. **✓** Verified session recording and audit logging
8. **⏳** RDP Guard needs to be started with PyRDP MITM backend
```

**Testing Plan**:
1. Add server, verify IP allocated and configured
2. Grant access to user
3. Connect from client to proxy_ip
4. Verify correct backend routing
5. Check session recording
6. Remove grant, verify IP still assigned
7. Remove server, verify IP released and removed from interface

---

## Phase 5: FreeIPA Integration ⏸️ NOT STARTED

### Task 10: FreeIPA Client Setup
- [ ] Install freeipa-client
- [ ] Join to FreeIPA domain
- [ ] Configure SSSD

### Task 11: FreeIPA User Sync
- [ ] Sync users from FreeIPA to local DB
- [ ] Map FreeIPA attributes to user table
- [ ] Periodic sync job (cron)

### Task 12: FreeIPA Authentication
- [ ] Replace password check with FreeIPA bind
- [ ] SSH key verification from FreeIPA
- [ ] Group-based access control

---

## Phase 6: Web Interface ⏸️ NOT STARTED

### Task 13: FastAPI Backend
- [ ] REST API endpoints
  - [ ] GET /users
  - [ ] POST /users
  - [ ] GET /servers
  - [ ] POST /servers
  - [ ] POST /grants
  - [ ] GET /grants
  - [ ] GET /audit-logs
  - [ ] GET /session-recordings

### Task 14: Web GUI
- [ ] Technology: React / Vue.js?
- [ ] User management page
- [ ] Server management page
- [ ] Grant management page (with temporal picker)
- [ ] Audit logs viewer
- [ ] Session recordings browser
- [ ] Real-time connection status

---

## Phase 7: Automation & Monitoring ⏸️ NOT STARTED

### Task 15: Grant Expiration Daemon
- [ ] Background service checking expired grants
- [ ] Auto-revoke access on expiration
- [ ] Notification to user before expiration
- [ ] Release unused proxy IPs

### Task 16: Systemd Services
- [ ] ssh_proxy.service
- [ ] rdp_guard.service
- [ ] rdp_wrapper.service
- [ ] grant_expiration.service

### Task 17: Monitoring & Alerting
- [ ] Prometheus metrics exporter
- [ ] Grafana dashboards
- [ ] Alert on access denials
- [ ] Alert on proxy failures
- [ ] Connection count metrics

### Task 18: Log Management
- [ ] Log rotation configuration
- [ ] Centralized logging (syslog/ELK?)
- [ ] Session recording cleanup policy

---

## Phase 8: Security Hardening ⏸️ NOT STARTED

### Task 19: Network Security
- [ ] Rate limiting (connection attempts per IP)
- [ ] DDoS protection
- [ ] Firewall rules (only allow from known networks)

### Task 20: Encryption
- [ ] TLS for RDP connections
- [ ] Encrypted session recordings
- [ ] Secure key storage

### Task 21: Audit & Compliance with dynamic routing
   - Agent forwarding ✓
   - Session recording ✓
   - Access control ✓
   - SCP/SFTP ✓
   - Listens on 0.0.0.0:22 ✓
   - Destination IP extraction ✓
   - Dynamic backend lookup via ip_allocations ✓
   - **Status**: Running in production

2. **RDP Proxy** - 100% functional in production (native PyRDP MITM modified)
   - **Modified PyRDP core**: /opt/jumphost/venv/lib/python3.13/site-packages/pyrdp/core/mitm.py
   - **Backup**: /opt/jumphost/venv/lib/python3.13/site-packages/pyrdp/core/mitm.py.backup
   - Access control based on source_ip only (simplified routing)
   - Uses deepcopy(config) for per-connection config isolation
   - Backend determined from user's grant in buildProtocol()
   - Session recording ✓
   - Listens on 0.0.0.0:3389 ✓
   - **Status**: Running in production (PID tracked in logs)
   - **Limitation**: If user has multiple grants, routes to first grant's server
   - **Future**: Add dest_ip verification by wrapping connectionMade() with state.effectiveTargetHost update

3. **Core Infrastructure**
   - Database schema ✓ (with permanent IP allocations)
   - Access control engine ✓ (with find_backend_by_proxy_ip)
   - IP pool manager ✓ (with allocate_permanent_ip)
   - CLI tool ✓ (assign-proxy-ip, remove-proxy-ip commands)

4. **Dynamic IP Pool System** ✓ COMPLETE
   - IP allocations table supports permanent server assignments ✓
   - allocate_permanent_ip() for server IPs ✓
   - CLI commands for IP management ✓
   - Network interface auto-configuration ✓
   - Backend lookup by destination IP ✓

### 🔄 In Progress
- None - all core systems operational!
   - Session recording ✓
   - Backend verification ✓

3. **Core Infrastructure**
   - Database schema ✓
   - Access control engine ✓
   - IP pool manag✓ DONE - Architecture refactor complete
   - ✓ Moved management SSH to port 2222
   - ✓ SSH proxy on 0.0.0.0:22 (already was)
   - ✓ RDP guard on 0.0.0.0:3389 (already was)
   - ✓ IP allocations via ip_allocations table (not proxy_ip column)
   - ✓ Destination IP lookup logic implemented (find_backend_by_proxy_ip)
   - ✓ SSH workflow tested end-to-end

2. **[HIGH]** ✓ DONE - RDP services started
   - ✓ Started rdp_guard.py on 0.0.0.0:3389
   - ✓ Started pyrdp-mitm on localhost:13389 → 10.30.0.140
   - TODO: Test RDP connection end-to-end
   - TODO: Configure PyRDP for Linux backend (10.0.160.4) if SSH proxy IP also needs RDP

3. **[MEDIUM]** Systemd service files for auto-start
   - jumphost-ssh.service
   - jumphost-rdp-guard.service  
   - jumphost-pyrdp-mitm.service
## Immediate Next Steps (Priority Order)

1. **[CRITICAL]** Refactor to 0.0.0.0 listening with destination IP extraction
   - Move management SSH to port 2222
   - Change SSH proxy to 0.0.0.0:22
   - Change RDP guard to 0.0.0.0:3389
   - ✓ SSH Proxy**: ~~Currently hardcodes backend to 10.0.160.4~~
   - ✓ FIXED: Uses destination IP via find_backend_by_proxy_ip()

2. **✓ RDP Guard**: ~~Currently hardcodes target_server to 10.30.0.140~~
   - ✓ FIXED: Uses destination IP via find_backend_by_proxy_ip()

3. **CLI**: No --source-ip option in add-user
   - TODO: Add optional --source-ip parameter

4. **✓ IP Pool**: ~~Not automatically used~~
   - ✓ FIXED: Manual assignment via assign-proxy-ip command
   - TODO: Consider auto-assignment on server creation

5. **Audit Logs**: user_id is nullable but should be set when known
   - TODO: Update audit logging to include user_id

6. **RDP Multi-Backend**: Simplified routing based on source_ip grant
   - ✓ Single PyRDP MITM instance handles all backends
   - ✓ No rdp_guard intermediate layer needed
   - ✓ Access control integrated directly in PyRDP factory
   - ⚠️ Limitation: Routes to first granted server if user has multiple grants
   - TODO: Implement full dest_ip verification in connectionMade() wrapper
   - TODO: Update state.effectiveTargetHost before server connection initiated stable)

---

## Technical Debt

1. **SSH Proxy**: Currently hardcodes backend to 10.0.160.4
   - Fix: Use destination IP to determine backend

2. **RDP Guard**: Currently hardcodes target_server to 10.30.0.140
   - Fix: Use destination IP to determine backend
 (Session 1 - Morning)
- ✅ SSH Proxy fully working with agent forwarding
- ✅ RDP Proxy fully working with PyRDP MITM
- ✅ RDP Guard proxy with access control
- ✅ Backend server verification in access control
- ✅ Audit logging for access granted/denied
- ⚠️ Identified architecture issue: shared IP for SSH/RDP
- 📝 Created documentation and roadmap

### 2026-01-02 (Session 2 - Afternoon) **MAJOR REFACTOR**
- ✅ Fixed database schema: user_id, source_ip, expires_at now nullable for permanent allocations
- ✅ Implemented allocate_permanent_ip() function for server IP assignments
- ✅ Fixed CLI assign-proxy-ip command (removed duplicate, uses allocate_permanent_ip)
- ✅ Fixed get_available_ips() to properly exclude permanent allocations
- ✅ Verified SSH proxy listens on 0.0.0.0:22 with destination IP extraction
- ✅ Verified RDP guard listens on 0.0.0.0:3389 with destination IP extraction
- ✅ Assigned proxy IPs: 10.0.160.129→Test-SSH-Server, 10.0.160.130→Windows-RDP-Server
- ✅ Configured IPs on network interface (ip addr add)
- ✅ Created users: p.mojski (Paweł Mojski), p.mojski.win (Paweł Mojski Windows)
- ✅ Created access grants: p.mojski→SSH (480 min), p.mojski.win→RDP (480 min)
- ✅ SSH proxy tested and working in production
- ✅ Started RDP Guard on 0.0.0.0:3389
- ✅ Started PyRDP MITM on localhost:13389 → Windows backend
- 🎯 **ARCHITECTURE REFACTOR COMPLETE** - Dynamic IP pool-based routing now operational
- 🚀 **SYSTEM FULLY OPERATIONAL** - Both SSH and RDP proxies running in production

**Current Production Status**:
- SSH Proxy: 0.0.0.0:22 (PID: 29078) → backends via IP pool routing (destination IP extraction) ✓
- RDP Proxy: 0.0.0.0:3389 (PID: ~34713) → backend via source_ip grant lookup (simplified) ✓
- Management SSH: 10.0.160.5:2222 ✓
- IP Allocations: 10.0.160.129→SSH Server, 10.0.160.130→RDP Server ✓
- **Active User**: p.mojski (Paweł Mojski) with 3 devices
  - Tailscale Linux (100.64.0.20): SSH as p.mojski/ideo
  - Biuro Linux (10.30.14.3): SSH as anyone
  - Tailscale Windows (100.64.0.39): RDP only
- **Access Control V2**: 3 active policies, all tests passing (13/13) ✓
- **Architecture**: Native PyRDP modification (no wrappers) for maximum performance

**Known Limitations**:
- RDP: Currently routes based on source_ip grant only (dest_ip not used)
- RDP: Multi-server grants per user will route to first granted server
- Solution attempted: dest_ip extraction in connectionMade() with state.effectiveTargetHost
- Issue: deepcopy(config) needed, state update timing critical
- **Next**: Integrate AccessControlEngineV2 with SSH/RDP proxies
- 🎯 **ARCHITECTURE REFACTOR COMPLETE** - Dynamic IP pool-based routing now operational but should be set when known
   - Fix: Update audit logging to include user_id

---

## Phase 5: Web Management Interface ✓ COMPLETE

### Task 10: Flask Web GUI ✓ COMPLETE
**Priority**: HIGH
**Status**: 🟢 PRODUCTION READY

**Goal**: Modern web-based management interface for all jumphost operations

#### Completed Features ✓

##### 1. Flask Application Setup ✓
- [x] Flask 3.1.2 with Blueprint architecture
- [x] Flask-Login for session management
- [x] Flask-WTF for form handling with CSRF protection
- [x] Flask-Cors for API endpoints
- [x] Bootstrap 5.3.0 frontend framework
- [x] Bootstrap Icons 1.11.0
- [x] Chart.js 4.4.0 for statistics
- [x] Custom CSS with service status indicators
- [x] Custom JavaScript with AJAX and Chart.js integration

##### 2. Authentication ✓
- [x] Login page with Bootstrap 5 design
- [x] Placeholder authentication (admin/admin)
- [x] Flask-Login integration with User model (UserMixin)
- [x] Session management with secure cookies
- [x] User loader from database
- [x] Logout functionality
- [x] Flash messages for user feedback
- [x] **Ready for Azure AD integration** (Flask-Azure-AD compatible)

##### 3. Dashboard ✓
- [x] Service status monitoring (SSH Proxy, RDP Proxy, PostgreSQL)
- [x] Process uptime calculation with psutil
- [x] Statistics cards:
  - Total users count
  - Total servers count
  - Active policies count
  - Today's connections count
- [x] Today's activity (granted vs denied with success rate)
- [x] Active sessions table (last 5 sessions)
- [x] Recent audit log (last 10 entries with color coding)
- [x] Auto-refresh stats every 30 seconds via AJAX
- [x] API endpoint: `/dashboard/api/stats` (JSON)

##### 4. User Management ✓
- [x] List all users with source IPs and policy counts
- [x] Add new user with multiple source IPs
- [x] Edit user details (username, email, active status)
- [x] View user details:
  - User information table
  - Source IP management (add/delete/toggle active)
  - Associated access policies
- [x] Delete user (cascade delete source IPs and policies)
- [x] Dynamic source IP fields on add form
- [x] Modal dialog for adding source IPs
- [x] Validation and error handling

##### 5. Server Management ✓
- [x] List all servers with proxy IPs and protocols
- [x] Add new server with automatic IP allocation
- [x] Edit server details (name, address, port, protocols, active status)
- [x] View server details:
  - Server information table
  - IP allocation details (proxy IP, NAT ports)
  - Group memberships list
- [x] Delete server
- [x] Enable/disable SSH and RDP protocols
- [x] Optional IP allocation checkbox on add form
- [x] Integration with IPPoolManager

##### 6. Group Management ✓
- [x] List all server groups
- [x] Create new group (name, description)
- [x] Edit group details
- [x] View group with members:
  - Group information table
  - Member servers list with protocols
  - Add/remove servers from group
- [x] Delete group
- [x] Available servers dropdown (excludes current members)
- [x] Modal dialog for adding servers to group

##### 7. Policy Management (Grant Wizard) ✓
- [x] List all access policies with filters:
  - Filter by user
  - Show/hide inactive policies
- [x] Grant access wizard with scope types:
  - **Group scope**: All servers in a group
  - **Server scope**: Single server (all protocols)
  - **Service scope**: Single server + specific protocol
- [x] User selection with dynamic source IP loading
- [x] Source IP dropdown (ANY or specific IP)
- [x] Protocol filtering (NULL, ssh, rdp)
- [x] SSH login restrictions (comma-separated list)
- [x] Temporal access:
  - Start time picker (default: now)
  - Duration in hours (default: permanent)
  - Auto-calculate end_time
- [x] Revoke policy (soft delete - sets is_active=false)
- [x] Delete policy (hard delete from database)
- [x] Dynamic form fields based on scope type
- [x] API endpoint: `/policies/api/user/<id>/ips` (JSON)

##### 8. Monitoring ✓
- [x] Main monitoring page with charts:
  - Hourly connections chart (last 24 hours) - Line chart
  - Top users chart (last 7 days) - Bar chart
- [x] Audit log viewer:
  - Pagination (50 entries per page)
  - Filters: action type, user, date range
  - Color-coded actions (granted=green, denied=red, closed=gray)
  - Full details per entry
- [x] API endpoints:
  - `/monitoring/api/stats/hourly` (JSON)
  - `/monitoring/api/stats/by_user` (JSON)
- [x] Chart.js integration with live updates
- [x] Pagination controls with page numbers

##### 9. UI/UX ✓
- [x] Base template with Bootstrap 5 navbar
- [x] Responsive design (mobile-friendly)
- [x] Dark navbar with brand logo
- [x] Active navigation highlighting
- [x] User dropdown menu with logout
- [x] Flash message container with auto-dismiss (5 seconds)
- [x] Service status indicators (pulsing green dot for running)
- [x] Stats cards with hover effects
- [x] Badges for status (active/inactive, protocols)
- [x] Color-coded audit log entries
- [x] Confirmation dialogs for delete operations
- [x] Loading spinners (prepared)
- [x] Error pages (404, 500)
- [x] Favicon route (prevents 404 errors)

##### 10. Backend Integration ✓
- [x] Database session management (before_request, teardown_request)
- [x] Flask g.db for per-request sessions
- [x] User model with Flask-Login UserMixin
- [x] Template filters:
  - `datetime` - Format datetime as string
  - `timeago` - Relative time (e.g., "5m ago")
- [x] Context processor for global variables
- [x] Error handlers (404, 500)
- [x] All blueprints with proper imports and sys.path fixes

**Files Created**:
```
/opt/jumphost/src/web/
├── app.py (142 lines)
├── blueprints/
│   ├── __init__.py
│   ├── auth.py (50 lines)
│   ├── dashboard.py (190 lines)
│   ├── users.py (150 lines)
│   ├── servers.py (110 lines)
│   ├── groups.py (140 lines)
│   ├── policies.py (150 lines)
│   └── monitoring.py (120 lines)
├── templates/
│   ├── base.html (137 lines)
│   ├── dashboard/index.html
│   ├── users/index.html, view.html, add.html, edit.html
│   ├── servers/index.html, view.html, add.html, edit.html
│   ├── groups/index.html, view.html, add.html, edit.html
│   ├── policies/index.html, add.html
│   ├── monitoring/index.html, audit.html
│   ├── auth/login.html
│   └── errors/404.html, 500.html
└── static/
    ├── css/style.css (185 lines)
    └── js/app.js (215 lines)
```

**Deployment**:
- Development: `python3 app.py` (port 5000)
- Production: `gunicorn --bind 0.0.0.0:5000 --workers 4 app:app`
- Reverse Proxy: nginx → http://localhost:5000

**Security**:
- CSRF protection on all forms
- Session cookies with HTTPOnly flag
- SQL injection prevention via SQLAlchemy ORM
- XSS prevention via Jinja2 autoescaping
- Login required decorators on all routes
- Flash messages for user feedback

**Known Limitations**:
- Authentication is placeholder (admin/admin)
- Need to integrate with Azure AD (Flask-Azure-AD)
- No real-time session monitoring (WebSocket)
- No session recording playback viewer yet
- No bulk operations (mass grant/revoke)

**Next Steps**:
- [ ] Azure AD integration (Flask-Azure-AD)
- [ ] Production deployment with gunicorn + systemd
- [ ] nginx reverse proxy configuration
- [ ] SSL/TLS certificates
- [ ] Session recording playback in web GUI
- [ ] Real-time monitoring with WebSockets
- [ ] Email notifications
- [ ] API documentation (Swagger/OpenAPI)

---

## Questions for User

1. **IP Allocation**: Automatycznie przy dodaniu serwera czy na żądanie?
2. **FreeIPA**: Jaki jest hostname/domain FreeIPA?
3. **Web GUI**: ✓ DONE - Flask + Bootstrap 5
4. **Monitoring**: Prometheus + Grafana OK?
5. **Session Recordings**: Jak długo trzymać? Auto-delete po X dniach?
6. **Azure AD**: Tenant ID, Client ID, Client Secret?
7. **Production**: nginx + SSL certificate?

---

## Changelog

### 2026-01-04 🎉 WEB GUI v1.1 RELEASE + SESSION TRACKING ⭐
- ✅ **Flask Web GUI** fully implemented with Bootstrap 5
- ✅ **7 Blueprints**: dashboard, users, servers, groups, policies, monitoring, auth
- ✅ **25+ Templates**: Complete CRUD interfaces for all resources
- ✅ **Dashboard**: Service monitoring, statistics, charts, recent activity
- ✅ **User Management**: CRUD + multiple source IPs per user
- ✅ **Server Management**: CRUD + automatic IP allocation
- ✅ **Group Management**: CRUD + N:M server relationships
- ✅ **Policy Wizard**: Grant access with group/server/service scopes
- ✅ **Monitoring**: Audit logs with pagination, connection charts
- ✅ **Authentication**: Placeholder (admin/admin) ready for Azure AD
- ✅ **Responsive Design**: Mobile-friendly Bootstrap 5 layout
- ✅ **AJAX Updates**: Dashboard stats refresh, Chart.js integration
- ✅ **Database Integration**: Flask-Login, session management, User model
- ✅ **REAL-TIME SESSION TRACKING** ⭐ (NEW in v1.1):
  - `sessions` table with 18 fields tracking active/historical connections
  - SSH session tracking: Creates on backend auth, closes on channel close
  - RDP session tracking: Creates on access grant, closes on TCP disconnect (observer pattern)
  - Dashboard "Active Sessions" shows: Protocol, User, Server, Backend IP, Source IP, SSH Agent, Duration
  - SSH subsystem detection (sftp, scp), SSH agent forwarding tracking
  - RDP multiplexing: Deduplikacja connections within 10s window
  - Recording path and file size tracked automatically
  - Duration calculation on session close
  - Multiple concurrent sessions supported independently
- ✅ **UTMP/WTMP INTEGRATION** 🎯 (NEW in v1.1):
  - Sessions logged to system utmp/wtmp for audit trail
  - SSH sessions: Registered as ssh0-ssh99 with backend user@server format
  - RDP sessions: Registered as rdp0-rdp99 with server name
  - Custom `jw` command (jumphost w) shows active proxy sessions
  - Compatible with system logging and monitoring tools
  - Automatic login/logout on session start/close
- 📦 **Total**: ~3,700 lines of Python/HTML/CSS/JS for web GUI + session tracking

### 2026-01-04 🎉 V2 PRODUCTION DEPLOYMENT
- ✅ **AccessControlEngineV2** fully deployed to production
- ✅ **Database migration** (8419b886bc6d) applied - 5 new V2 tables
- ✅ **SSH Proxy** integrated with V2 (check_access_v2 with protocol='ssh')
- ✅ **RDP Proxy** (PyRDP MITM) integrated with V2 (check_access_v2 with protocol='rdp')
- ✅ **CLI V2** implemented - 11 new management commands
- ✅ **Production user** p.mojski configured with 3 source IPs and 3 policies
- ✅ **Transparent auth** working: SSH agent forwarding + password fallback
- ✅ **All tests passed**: 13/13 production scenarios validated
- ✅ **Documentation**: FLEXIBLE_ACCESS_CONTROL_V2.md created
- 📦 **Backup**: ssh_proxy.py.working_backup_20260104_113741

### 2026-01-02
- ✅ SSH Proxy fully working with agent forwarding
- ✅ RDP Proxy fully working with PyRDP MITM
- ✅ RDP Guard proxy with access control
- ✅ Backend server verification in access control
- ✅ Audit logging for access granted/denied
- ⚠️ Identified architecture issue: shared IP for SSH/RDP
- 📝 Created documentation and roadmap

---

## Notes

### PyRDP Patch Location
- File: `/opt/jumphost/venv/lib/python3.13/site-packages/pyrdp/enum/rdp.py`
- Backup: `/opt/jumphost/venv/lib/python3.13/site-packages/pyrdp/enum/rdp.py.backup`
- Changes: Added `_missing_()` classmethod and `RDP10_12 = 0x80011`

### PyRDP MITM Modification
- File: `/opt/jumphost/venv/lib/python3.13/site-packages/pyrdp/core/mitm.py`
- Backup: `/opt/jumphost/src/proxy/rdp_mitm_backup.py.orig` (2026-01-04)
- Changes: 
  - Added jumphost module imports (database, access_control, Session model)
  - Modified `MITMServerFactory.buildProtocol()` to check source_ip access
  - Uses `deepcopy(config)` for per-connection backend configuration
  - Sets `config.targetHost` from grant before creating RDPMITM
  - Integrated audit logging for RDP connections
  - **SESSION TRACKING** (NEW v1.1): ⭐
    - Creates Session record in database on access granted
    - TCP observer pattern for disconnect detection (client & server)
    - RDP multiplexing: Reuses session for connections within 10s window
    - Observer references preserved in `protocol._jumphost_client_observer` & `_server_observer`
    - Calculates duration and recording file size on session close
    - Multiple concurrent sessions supported independently

### Database Manual Operations
```python
# Add user with source_ip
from src.core.database import SessionLocal, User
db = SessionLocal()
user = User(username='name', email='email@example.com', 
            full_name='Full Name', source_ip='100.64.0.X', is_active=True)
db.add(user)
db.commit()
db.close()
```

### Useful Commands
```bash
# Check active connections
ss -tnp | grep -E ':(22|3389)'

# View audit logs
psql -U jumphost -d jumphost -c "SELECT * FROM audit_logs ORDER BY timestamp DESC LIMIT 10;"

# Check allocated IPs
psql -U jumphost -d jumphost -c "SELECT * FROM ip_allocations WHERE released_at IS NULL;"
```

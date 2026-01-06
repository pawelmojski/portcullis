# 🚀 Jumphost Project - SSH/RDP Proxy with Web Management Interface

**Production-ready SSH and RDP jumphost with policy-based access control, session recording, dynamic IP routing, and Flask Web GUI.**

[![Status](https://img.shields.io/badge/status-production-brightgreen)]()
[![Version](https://img.shields.io/badge/version-1.1-blue)]()
[![Python](https://img.shields.io/badge/python-3.13-blue)]()
[![License](https://img.shields.io/badge/license-Proprietary-red)]()

---

## 📋 Overview

Jumphost is a comprehensive SSH and RDP proxy solution designed for enterprise environments requiring:
- **Web Management Interface** - Modern Flask-based GUI with Bootstrap 5
- **Granular access control** based on source IP, user, server groups, and protocols
- **Session recording** for compliance and audit purposes
- **Temporal permissions** with automatic expiration
- **Transparent authentication** with SSH agent forwarding support
- **Dynamic backend routing** using IP allocation pool
- **Real-time monitoring** with charts and audit logs

### Architecture

```
Client (100.64.0.X)
    ↓
Jumphost (10.0.160.5)
    ├─ Web GUI (Port 5000) ───→ Management Interface
    ├─ SSH Proxy (Port 22) ───→ Backend SSH Server (10.30.0.X:22)
    └─ RDP Proxy (Port 3389) ─→ Backend RDP Server (10.30.0.X:3389)
    
Access Control V2:
    • Multiple source IPs per user
    • Server groups (tags)
    • Group/Server/Service-level permissions
    • Protocol filtering (SSH, RDP, both)
    • SSH login restrictions
    
Web Management:
    • User management (CRUD + source IPs)
    • Server management (CRUD + IP allocation)
    • Group management (N:M relationships)
    • Policy wizard (grant/revoke access)
    • Dashboard (service status, statistics, charts)
    • Monitoring (audit logs, connection charts)
```

---

## ✨ Features

### Web Management Interface 🆕
- ✅ **Flask Web GUI** - Modern Bootstrap 5 interface
- ✅ **Dashboard** - Service status, statistics, recent activity
- ✅ **User Management** - CRUD operations + multiple source IPs
- ✅ **Server Management** - CRUD + automatic IP allocation
- ✅ **Group Management** - Create groups, assign servers (N:M)
- ✅ **Policy Wizard** - Grant access with scope (group/server/service)
- ✅ **Monitoring** - Audit logs with filters, connection charts
- ✅ **Authentication** - Placeholder (admin/admin) ready for Azure AD
- ✅ **Responsive Design** - Mobile-friendly layout

### Access Control V2
- ✅ **Multiple Source IPs** - Users can connect from home, office, VPN, etc.
- ✅ **Server Groups** - Organize servers with tags, N:M relationships
- ✅ **Granular Permissions** - Group-level, server-level, or service-level
- ✅ **Protocol Filtering** - Restrict to SSH, RDP, or allow both
- ✅ **SSH Login Restrictions** - Control which system accounts can be used
- ✅ **Temporal Access** - Time-limited permissions with automatic expiration

### SSH Proxy
- ✅ **Transparent Authentication** - SSH agent forwarding + password fallback
- ✅ **PTY Support** - Full terminal emulation
- ✅ **SCP/SFTP** - File transfer protocols supported
- ✅ **Session Recording** - Asciinema format for playback
- ✅ **Dynamic Backend Routing** - IP-based destination lookup

### RDP Proxy
- ✅ **PyRDP MITM** - Full RDP protocol support
- ✅ **Session Recording** - PyRDP custom format with replay capability
- ✅ **TLS Support** - Encrypted connections
- ✅ **Channel Support** - rdpdr, rdpsnd, cliprdr, drdynvc
- ✅ **Smart Card Redirection** - Hardware token support

### Infrastructure
- ✅ **PostgreSQL Database** - Robust storage with JSONB support
- ✅ **Alembic Migrations** - Version-controlled schema changes
- ✅ **CLI Management** - Complete command-line interface
- ✅ **Web GUI** - Flask-based management interface
- ✅ **Audit Logging** - All access attempts logged to database

---

## 🎨 Web Interface

Access the web management interface at `http://10.0.160.5:5000`

**Default credentials**: `admin` / `admin`

### Features:

#### 📊 Dashboard
- Service status indicators (SSH Proxy, RDP Proxy, PostgreSQL)
- Statistics cards (users, servers, policies, connections)
- Today's activity summary with success rate
- Active sessions list
- Recent audit log entries

#### 👥 User Management
- List all users with source IPs and policy counts
- Add new users with multiple source IPs
- Edit user details
- View user details (info, source IPs, policies)
- Add/remove/toggle source IPs per user
- Delete users

#### 🖥️ Server Management
- List all servers with proxy IPs and protocols
- Add new servers with automatic IP allocation
- Edit server details
- View server details (info, IP allocation, group memberships)
- Enable/disable SSH and RDP protocols
- Delete servers

#### 📁 Group Management
- List all server groups
- Create new groups
- Edit group details
- View group members
- Add/remove servers from groups
- Delete groups

#### 🔑 Policy Management
- List all access policies with filters
- Grant access wizard with scope types:
  - **Group**: All servers in a group
  - **Server**: Single server (all protocols)
  - **Service**: Single server + specific protocol
- Protocol filtering (SSH, RDP, or both)
- SSH login restrictions (specific system accounts)
- Temporal access (duration in hours)
- Revoke or delete policies

#### 📈 Monitoring
- Audit log viewer with pagination (50 per page)
- Filters: action type, user, date range
- Connection charts:
  - Hourly connections (last 24 hours)
  - Top users by connections (last 7 days)
- Chart.js integration for live updates

---

## 🚀 Quick Start

### Prerequisites
- Debian 13 (Trixie) or compatible
- Python 3.13+
- PostgreSQL 17+
- Network: 10.0.160.128/25 IP pool

### Installation

```bash
# Clone repository
git clone /opt/jumphost
cd /opt/jumphost

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Setup database
createdb jumphost
alembic upgrade head

# Configure environment
cp .env.example .env
# Edit .env with your database credentials
```

### Starting Services

```bash
# SSH Proxy
sudo python3 /opt/jumphost/src/proxy/ssh_proxy.py &

# RDP Proxy
sudo /opt/jumphost/venv/bin/pyrdp-mitm \
  -a 0.0.0.0 -l 3389 \
  -o /var/log/jumphost/rdp_recordings \
  127.0.0.1 > /var/log/jumphost/rdp_proxy.log 2>&1 &
```

---

## 📖 Usage Examples

### User Management

```bash
# Add user
./src/cli/jumphost_cli.py add-user john --full-name "John Doe" --email john@example.com

# Add source IPs for user
./src/cli/jumphost_cli.py add-user-ip john 192.168.1.100 --label "Home"
./src/cli/jumphost_cli.py add-user-ip john 10.0.0.50 --label "Office"
./src/cli/jumphost_cli.py add-user-ip john 100.64.0.10 --label "VPN"
```

### Server Management

```bash
# Add server
./src/cli/jumphost_cli.py add-server prod-db-01 10.30.0.100

# Create server group
./src/cli/jumphost_cli.py add-server-group "Production DB" --description "Production databases"

# Add server to group
./src/cli/jumphost_cli.py add-server-to-group prod-db-01 "Production DB"
```

### Access Policies

```bash
# Grant group-level access (all servers in group)
./src/cli/jumphost_cli.py grant-policy john group "Production DB" --duration-hours 8

# Grant server-level access (specific server, all protocols)
./src/cli/jumphost_cli.py grant-policy mary server bastion-host --duration-hours 24

# Grant service-level access (specific server + protocol)
./src/cli/jumphost_cli.py grant-policy bob service app-server-01 --protocol ssh

# Grant with SSH login restrictions
./src/cli/jumphost_cli.py grant-policy alice server db-01 \
  --protocol ssh \
  --ssh-logins postgres --ssh-logins monitoring
```

### Connecting as Client

```bash
# SSH with agent forwarding (recommended)
ssh -A user@10.0.160.129

# SSH with password (if agent forwarding not available)
ssh -o PubkeyAuthentication=no user@10.0.160.129

# RDP (Windows client)
mstsc /v:10.0.160.130

# RDP (Linux client)
xfreerdp /v:10.0.160.130 /u:Administrator
```

---

## 🗂️ Project Structure

```
jumphost/
├── src/
│   ├── core/
│   │   ├── access_control_v2.py    # Access control engine
│   │   ├── database.py             # ORM models
│   │   ├── ip_pool.py              # IP allocation manager
│   │   └── nat_manager.py          # NAT configuration
│   ├── proxy/
│   │   ├── ssh_proxy.py            # SSH proxy server
│   │   └── rdp_wrapper.sh          # RDP startup script (systemd)
│   └── cli/
│       └── jumphost_cli.py         # Command-line interface
├── alembic/
│   └── versions/                   # Database migrations
├── venv/                           # Python virtual environment
├── logs/                           # Application logs
├── DOCUMENTATION.md                # General documentation
├── FLEXIBLE_ACCESS_CONTROL_V2.md   # V2 system documentation
├── ROADMAP.md                      # Project roadmap
└── MILESTONE_v1.0.md               # Release notes

External Modifications:
└── venv/lib/python3.13/site-packages/pyrdp/core/mitm.py
```

---

## 🔧 Configuration

### Database Schema V2

**New Tables:**
- `user_source_ips` - Multiple IPs per user
- `server_groups` - Logical server groupings
- `server_group_members` - N:M server-to-group relationships
- `access_policies` - Flexible access rules
- `policy_ssh_logins` - SSH login restrictions

### IP Allocation Pool

- Range: `10.0.160.128/25`
- Proxy IPs: Allocated from pool
- Backend IPs: Mapped in `ip_allocations` table

### Session Recording

**SSH Sessions:**
- Location: `/var/log/jumphost/ssh/`
- Format: Asciinema JSON
- Playback: `asciinema play <file>`

**RDP Sessions:**
- Location: `/var/log/jumphost/rdp_recordings/replays/`
- Format: PyRDP (.pyrdp)
- Playback: `pyrdp-player.py <file>`

---

## 🧪 Testing

### Production Validation

**Test User:** p.mojski  
**Test Date:** 2026-01-04  
**Results:** 13/13 scenarios passed ✅

**Test Coverage:**
- SSH authentication (agent forwarding + password)
- RDP connection and session recording
- Group-level access control
- Server-level access control
- Service-level access control (protocol filtering)
- SSH login restrictions
- Access denials (no policy, wrong protocol, wrong login)

---

## 📊 Performance

- **SSH Latency:** ~10-20ms overhead
- **RDP Latency:** ~50-100ms overhead
- **Max Concurrent Sessions:** Tested up to 10
- **Session Recording Impact:** ~5% CPU per active session
- **Denied Connection Handling:** ~100-120ms (graceful close)

---

## 🔒 Security Considerations

### Access Control
- All access attempts logged to database
- Source IP verification on every connection
- Temporal permissions with automatic expiration
- Protocol-level filtering prevents unauthorized service access

### Session Recording
- All sessions recorded for audit purposes
- Recordings stored securely with restricted access
- Replay capability for investigation

### Authentication
- SSH agent forwarding for key-based auth
- Password fallback for compatibility
- No password storage (pass-through to backend)

---

## 🐛 Known Issues & Limitations

### RDP Proxy
- Denied connections initialize PyRDP before close (~100ms overhead)
- Workaround considered: separate listeners per IP (future optimization)
- Current solution adequate for enterprise use case

### SSH Proxy
- Agent forwarding required for pubkey auth
- Clear error messages guide users to correct command

---

## 📝 Changelog

### v1.0 (2026-01-04) - Production Release
- ✅ Flexible Access Control V2 fully integrated
- ✅ SSH login forwarding fix (use client login, not DB username)
- ✅ RDP destination IP extraction from socket
- ✅ Graceful denied connection handling
- ✅ Production testing: 13/13 scenarios passed
- ✅ Complete documentation

---

## 🛠️ Development

### Critical Files Modified

**Core Application:**
- `/opt/jumphost/src/proxy/ssh_proxy.py` - SSH login forwarding + agent auth
- `/opt/jumphost/src/core/access_control_v2.py` - V2 access control engine

**External Dependencies:**
- `/opt/jumphost/venv/lib/python3.13/site-packages/pyrdp/core/mitm.py` - Access control integration
- Backup: `pyrdp_mitm_py_MODIFIED_v1.0_20260104.py`

### Backups
- Working SSH proxy: `ssh_proxy.py.working_backup_20260104_113741`
- Full project: `/opt/jumphost-v1.0-20260104_120754.tar.gz`
- Modified PyRDP: `pyrdp_mitm_py_MODIFIED_v1.0_20260104.py`

### Git Repository
```bash
# View history
git log --oneline

# Show tags
git tag -l

# View specific release
git show v1.0
```

---

## 🚧 Future Roadmap

- [ ] Systemd service files (auto-start on boot)
- [ ] fail2ban integration (DOS protection)
- [ ] FreeIPA integration (centralized user management)
- [ ] Web UI for policy management
- [ ] Real-time session monitoring dashboard
- [ ] Multi-factor authentication support
- [ ] Automatic IP allocation on policy grant
- [ ] Performance optimization: separate listeners per IP

---

## 📞 Support

**Contact:** p.mojski@ideosoftware.com  
**Documentation:** See `FLEXIBLE_ACCESS_CONTROL_V2.md` for detailed API docs  
**Logs:** `/var/log/jumphost/` (ssh/, rdp/, rdp_proxy.log)  
**Database:** PostgreSQL on localhost:5432, database: jumphost

---

## 📄 License

Proprietary - Internal use only  
© 2026 IDEO Software. All rights reserved.

---

## 🏆 Credits

**Development:** Paweł Mojski (p.mojski@ideosoftware.com)  
**Testing:** Production validation with real-world scenarios  
**Duration:** 4 days (rapid development cycle)  
**Lines of Code:** ~3500 Python, ~500 SQL  
**External Dependencies:** Paramiko, PyRDP, SQLAlchemy, PostgreSQL

---

*Built with ❤️ for enterprise security and compliance*

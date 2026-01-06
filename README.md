# 🏰 Portcullis - SSH/RDP Gateway with Policy-Based Access Control

**A transparent security gateway that stands between your users and backend servers, enforcing access policies, recording sessions, and providing centralized management.**

[![Status](https://img.shields.io/badge/status-production-brightgreen)]()
[![Version](https://img.shields.io/badge/version-1.8-blue)]()
[![Python](https://img.shields.io/badge/python-3.13-blue)]()

---

## 💡 What is Portcullis?

Imagine you have 50 servers and 20 employees. Each employee needs access to different servers at different times. Traditional approach: create accounts on each server, manage SSH keys, remember who has access where, manually revoke when someone leaves.

**Portcullis sits in the middle** and solves this:

```
User's Computer → Portcullis Gateway → Backend Server
    (anywhere)        (one place)         (10.0.x.x)
```

From user's perspective: `ssh server.company.com` - works like normal SSH/RDP.
Behind the scenes: Portcullis checks "does this user have permission RIGHT NOW?" and either allows or denies.

### Key Concept: Time-Limited Access Grants

Instead of permanent accounts, you **grant temporary access**:

```bash
# Give Alice 8 hours access to production database
portcullis grant alice --server prod-db-01 --duration 8h

# Alice can now: ssh alice@prod-db-01
# After 8 hours: Access automatically expires, no cleanup needed
```

Everything is:
- ✅ **Centralized** - one place to manage all access
- ✅ **Temporary** - access expires automatically
- ✅ **Audited** - every connection recorded
- ✅ **Flexible** - grant access to groups, single servers, or specific protocols

---

## 🎯 How It Works

### 1. The Gateway (Portcullis)

Portcullis runs on a single server (e.g., `gateway.company.com`):
- **Port 22** - SSH traffic goes through here
- **Port 3389** - RDP traffic goes through here
- **Port 5000** - Web management interface

### 2. Access Grants (Policies)

You manage access through **policies** (grants):

**Example: Grant group access**
```
User: john
Target: All servers in "Production Databases" group
Protocol: SSH only
Duration: 24 hours
SSH logins: postgres, readonly
```

When John tries to connect:
```bash
john@laptop:~$ ssh postgres@prod-db-01.company.com
# ↓ Connection goes to Portcullis
# ↓ Portcullis checks: Does john have active grant for prod-db-01?
# ✅ YES - proxy connection to real prod-db-01 server
# ❌ NO - show friendly "access denied" message
```

### 3. What User Sees

**WITH ACCESS GRANT:**
```bash
$ ssh myuser@target-server
# Works exactly like normal SSH
# User doesn't even know Portcullis is there
```

**WITHOUT ACCESS GRANT:**
```
+====================================================================+
|                          ACCESS DENIED                             |
+====================================================================+

  Dear user,

  There is no active access grant for your IP address: 100.64.0.20

  Reason: No matching access policy

  Please contact your administrator to request access.
```

### 4. Session Recording

Every connection is recorded:
- **SSH sessions** - Full terminal recording (like asciinema)
- **RDP sessions** - Video recording with playback
- **Audit log** - Who connected when, from where, to which server

Web interface shows:
- Active sessions (who is connected right now)
- Session history (search by user, server, date)
- Live view (watch SSH session in real-time)
- Recording playback

---

## 🚀 Real-World Example

### Scenario: Emergency Database Access

**9:00 AM** - Database issue reported

**Team Lead:**
```bash
# Grant DBA access for 4 hours
portcullis grant alice --server prod-db-01 --duration 4h --protocol ssh
```

**Alice (from home, VPN, or office):**
```bash
alice@laptop:~$ ssh postgres@prod-db-01
# Works immediately, no keys to copy, no server accounts to create
```

**1:00 PM** - Issue resolved, access expires automatically

**Later** - Team lead reviews:
- Web UI shows Alice connected 9:15-10:30
- Can watch terminal recording to see what commands were run
- Audit log shows connection from IP 100.64.0.25

---

## 🎨 Web Management Interface

Access at `http://gateway.company.com:5000`

### Dashboard
- 🟢 Service status (SSH Proxy, RDP Proxy running)
- 📊 Quick stats (15 users, 42 servers, 8 active sessions)
- 📅 Today's activity (23 connections, 2 denied, 91% success rate)
- 🔄 Auto-refresh every 5 seconds

### Grant Access Wizard

**Simple 3-step process:**

1. **Who?** Select user (or create new)
2. **Where?** Choose:
   - Server group (e.g., "All production DBs")
   - Single server (e.g., "app-server-01")
   - Specific service (e.g., "db-01 SSH only")
3. **How long?** Enter duration: `2h`, `3d`, `1w`, or `permanent`

**Advanced options:**
- Protocol filtering (SSH only, RDP only, or both)
- SSH login restrictions (only `postgres` and `readonly` accounts)
- Schedule windows (Monday-Friday 9-17)

### Search Everything (Mega-Wyszukiwarka) 🔍

Unified search across all data:
- Search by username, server name, IP address
- Filter by protocol, status (active/denied), date range
- Auto-refresh every 2 seconds (see new sessions appear live)
- Export to CSV for reporting

**Examples:**
```
Search: "alice"          → All sessions by user alice
Search: "10.0.1.50"      → All connections to/from this IP
Search: "#42"            → Policy #42 details
Search: "denied"         → All denied connection attempts
```

---

## 🏗️ Architecture

### Simple Deployment (Current)

```
┌─────────────────────────────────────────┐
│         Portcullis Gateway              │
│  ┌─────────────┐  ┌──────────────────┐ │
│  │  SSH Proxy  │  │   RDP Proxy      │ │
│  │   (port 22) │  │   (port 3389)    │ │
│  └─────────────┘  └──────────────────┘ │
│  ┌─────────────┐  ┌──────────────────┐ │
│  │  Flask Web  │  │   PostgreSQL     │ │
│  │ (port 5000) │  │  (policies, logs)│ │
│  └─────────────┘  └──────────────────┘ │
└─────────────────────────────────────────┘
           │
           │ Routes to backend servers
           ↓
    ┌──────────────┐  ┌──────────────┐
    │  Backend     │  │  Backend     │
    │  Server 1    │  │  Server 2    │
    └──────────────┘  └──────────────┘
```

### Distributed Architecture (v1.9 - Coming Soon)

```
         ┌──────────────────────────┐
         │    Tower (Control)       │
         │  - Web UI                │
         │  - Policy Database       │
         │  - API Server            │
         └────────────┬─────────────┘
                      │
        ┬─────────────┼─────────────┬
        │             │             │
   ┌────▼───┐    ┌───▼────┐    ┌───▼────┐
   │ Gate 1 │    │ Gate 2 │    │ Gate 3 │
   │  DMZ   │    │ Cloud  │    │ Office │
   └────────┘    └────────┘    └────────┘
```

**Use case:** Install Portcullis gate in different network segments (DMZ, cloud, office) - all managed from single Tower.

---

## 💎 Features

### Access Control
- ✅ **Multiple source IPs per user** - Home, office, VPN, mobile
- ✅ **Server groups** - Grant access to entire groups ("All production servers")
- ✅ **Granular scope** - Group level, server level, or protocol level
- ✅ **Protocol filtering** - SSH only, RDP only, or both
- ✅ **SSH login restrictions** - Allow only specific system accounts
- ✅ **Temporal access** - Time-limited with automatic expiration
- ✅ **Schedule windows** - Access only Mon-Fri 9-17, recurring weekly
- ✅ **Recursive groups** - User groups with inheritance

### Session Management
- ✅ **Live monitoring** - See active sessions in real-time
- ✅ **SSH live view** - Watch terminal session as it happens
- ✅ **Recording** - SSH (terminal) and RDP (video)
- ✅ **Playback** - Review past sessions
- ✅ **Search** - Find sessions by user, server, time, status
- ✅ **Auto-refresh** - Dashboard updates every 5s, search every 2s

### Auditing
- ✅ **Connection attempts** - Both successful and denied
- ✅ **Policy changes** - Full audit trail with history
- ✅ **Denial reasons** - Clear logging why access was denied
- ✅ **Export** - CSV export for reporting/compliance

### User Experience
- ✅ **Transparent** - Works with standard SSH/RDP clients
- ✅ **Friendly errors** - Clear messages when access denied
- ✅ **No config** - Users just `ssh server`, no special setup
- ✅ **Agent forwarding** - SSH keys work naturally

---

## 🔧 Quick Start

### Installation

```bash
# Install system dependencies
sudo apt install postgresql python3.13 python3-pip python3-venv

# Clone repository
git clone https://github.com/yourusername/portcullis
cd portcullis

# Setup virtual environment
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Initialize database
sudo -u postgres createdb portcullis
alembic upgrade head

# Start services
sudo systemctl enable --now portcullis-ssh-proxy
sudo systemctl enable --now portcullis-rdp-proxy
sudo systemctl enable --now portcullis-flask
```

### First Use

1. **Access web interface:** http://your-server:5000
2. **Add yourself as user:**
   - Users → Add User
   - Enter your name, email
   - Add your source IP (see "My IP: X.X.X.X" in top right)
3. **Add a backend server:**
   - Servers → Add Server
   - Name: `test-server`, IP: `10.0.1.100`
4. **Grant yourself access:**
   - Policies → Grant Access
   - Select yourself, select server, duration `1h`
5. **Test connection:**
   ```bash
   ssh your-username@test-server
   ```

---

## 📖 Common Use Cases

### 1. Contractor Access

**Problem:** Need to give contractor temporary access to specific servers.

**Solution:**
```bash
# Add contractor
portcullis user add contractor-john --email john@external.com
portcullis user add-ip contractor-john 203.0.113.50 --label "Contractor VPN"

# Grant 2-week access to dev servers only
portcullis grant contractor-john --group "Development Servers" --duration 14d

# Access automatically expires, no cleanup needed
```

### 2. On-Call Rotation

**Problem:** Different person has production access each week.

**Solution:**
```bash
# Week 1: Alice on-call
portcullis grant alice --group "Production" --duration 7d

# Week 2: Bob on-call (Alice's grant already expired)
portcullis grant bob --group "Production" --duration 7d
```

### 3. Emergency Access

**Problem:** Database down at 2 AM, need DBA access NOW.

**Solution:**
```bash
# From phone via curl:
curl -X POST https://gateway/api/v1/grant \\
  -H "Authorization: Bearer \$TOKEN" \\
  -d '{"user":"dba-alice","server":"prod-db","duration":"4h"}'

# DBA can connect immediately from anywhere
```

### 4. Compliance Audit

**Problem:** "Show me everyone who accessed production last month."

**Solution:**
- Web UI → Search
- Filter: server_group="Production", date_from="2025-12-01"
- Export → CSV
- Done. Full audit trail with session recordings.

---

## 🎓 Key Concepts

### Policies (Grants)

A policy is: "User X can access Target Y via Protocol Z for Duration D"

**Components:**
- **User** - Who gets access
- **Target** - Server group, single server, or specific service
- **Protocol** - SSH, RDP, or both
- **Duration** - How long (or permanent)
- **Schedule** (optional) - Time windows (e.g., business hours only)
- **SSH logins** (optional) - Restrict which system accounts

### User Source IPs

Users can have multiple source IPs:
- Home: `192.168.1.100`
- Office: `10.0.50.25`
- VPN: `100.64.0.10`
- Mobile: `203.0.113.5`

When user connects from ANY of these IPs, Portcullis recognizes them.

### Server Groups

Organize servers logically:
- "Production Databases"
- "Development Servers"  
- "DMZ Web Servers"

Grant access to entire group instead of individual servers.

### Session States

- **Active** - User currently connected
- **Closed** - Session ended normally
- **Denied** - Connection attempt blocked (no policy)

---

## 🔒 Security Features

### Defense in Depth

1. **Network Level** - Only Portcullis accessible from internet
2. **Policy Level** - Fine-grained access control
3. **Protocol Level** - Filter SSH vs RDP
4. **Account Level** - Restrict SSH system accounts
5. **Time Level** - Automatic expiration
6. **Audit Level** - Everything logged

### What Gets Recorded

- Connection attempts (successful and denied)
- Source IP, destination server, protocol
- Duration, bytes transferred
- Full session recording (terminal or video)
- Policy that granted/denied access
- Denial reason if blocked

### Access Denial

When access denied, user sees:
- Friendly message (not cryptic error)
- Reason why denied
- How to request access

Portcullis logs:
- Attempted user, server, source IP
- Denial reason (no policy, expired, wrong protocol, etc.)
- Timestamp

---

## 🛠️ Advanced Features

### Port Forwarding Control

Control who can do SSH port forwarding:

```bash
# Grant with port forwarding allowed
portcullis grant alice --server bastion \\
  --allow-port-forwarding local,remote,dynamic

# Grant without port forwarding
portcullis grant bob --server app-server \\
  --no-port-forwarding
```

### Schedule-Based Access

Access only during business hours:

```bash
portcullis grant alice --server prod-db \\
  --schedule "Mon-Fri 09:00-17:00" \\
  --timezone "Europe/Warsaw"
```

Recurring weekly - user can connect anytime within schedule, automatically blocked outside.

### TPROXY Mode (v1.9)

Transparent proxy for routers (Tailscale, VPN gateways):

```bash
# User thinks they're connecting directly
ssh user@10.50.1.100

# Iptables routes through Portcullis transparently
iptables -t mangle -A PREROUTING -p tcp --dport 22 \\
  -j TPROXY --on-port 2222

# Portcullis sees original destination IP, checks policy
```

---

## 🚧 Roadmap

### v1.9 - Distributed Architecture & TPROXY
- Multi-gate deployment (DMZ, cloud, office)
- Tower (control plane) + Gate (data plane) separation
- TPROXY transparent proxy mode
- Local caching for offline resilience

### v2.0 - CLI & Automation
- Full curl-based CLI tool
- Token-based API authentication
- Bash completion
- Webhook notifications (Slack, Teams)
- FreeIPA/LDAP integration

---

## 📊 Monitoring & Operations

### Health Check

```bash
# Check all services
systemctl status portcullis-*

# View logs
journalctl -u portcullis-ssh-proxy -f
tail -f /var/log/portcullis/ssh_proxy.log
```

### Metrics

Web dashboard shows:
- Active sessions count
- Connections per hour (chart)
- Top users by activity
- Denied attempts
- Policy expiration warnings

### Maintenance

```bash
# Backup database
pg_dump portcullis > backup.sql

# View session recordings
ls /var/recordings/portcullis/ssh/
ls /var/recordings/portcullis/rdp/

# Clean old recordings (>90 days)
find /var/recordings/ -mtime +90 -delete
```

---

## 🤝 Contributing

Contributions welcome! Areas we'd love help with:
- FreeIPA/LDAP integration
- Ansible playbooks for deployment
- Terraform modules
- Kubernetes Helm charts
- Additional authentication methods

---

## 🎯 TL;DR

**Portcullis = Security gateway that:**
- Sits between users and servers
- Enforces temporary access policies
- Records every session
- Shows everything in web UI
- Works with normal SSH/RDP clients

**One command to grant access:**
```bash
portcullis grant alice --server prod-db --duration 8h
```

**One place to see everything:**
```
http://gateway:5000
```

That's it. Simple concept, powerful execution. 🏰

---

*Built for security teams who value simplicity and auditability.*

# 🚪 Inside - Gateway with Time-Based Access Control

**A transparent security gateway that controls who can be inside your infrastructure, when, and for how long.**

[![Status](https://img.shields.io/badge/status-production-brightgreen)]()
[![Version](https://img.shields.io/badge/version-1.8-blue)]()
[![Python](https://img.shields.io/badge/python-3.13-blue)]()

---

## 🎯 Mental Model: Not "Access", but "Being Inside"

**Inside doesn't manage identities. Inside manages when real people can be inside your infrastructure.**

This is the difference that:
- ✅ Distinguishes Inside from Teleport, PAMs, and ZTNA
- ✅ Explains why deployment takes 1 hour, not months
- ✅ Makes it instantly understandable for everyone

### Instant Mental Clarity

Not "access", not "identity", not "control".

Everyone immediately understands:
- 👤 **Who is inside** right now
- 🎫 **Who can be inside** (and when)
- 🎬 **What they do while inside**
- ⏰ **When they stop being inside**

No need to explain architecture.

### Perfect Operational Language

This is critically important.

*"Who is inside production right now?"*

*"He was inside for 30 minutes."*

*"This stay is inside until 14:30."*

*"Nobody is allowed inside without a grant."*

Sounds like reality, not like a system.

---

## 💡 What is Inside?

Imagine you have 50 servers and 20 employees. Each person needs access to different servers at different times. Traditional approach: create accounts on each server, manage SSH keys, remember who has access where, manually revoke when someone leaves.

**Inside sits in the middle** and solves this:

```
Person's Computer → Inside Gateway → Backend Server
    (anywhere)       (one place)        (10.0.x.x)
```

From person's perspective: `ssh server.company.com` - works like normal SSH/RDP.
Behind the scenes: Inside checks "does this person have a valid grant RIGHT NOW?" and either allows or denies.

### Key Concept: Time-Limited Grants

Instead of permanent accounts, you **grant temporary access**:

```bash
# Give Alice 8 hours to be inside production database
inside grant alice --server prod-db-01 --duration 8h

# Alice can now: ssh alice@prod-db-01
# After 8 hours: Access automatically expires, no cleanup needed
```

Everything is:
- ✅ **Centralized** - one place to manage all access
- ✅ **Temporary** - grants expire automatically
- ✅ **Audited** - every stay inside is recorded
- ✅ **Flexible** - grant access to groups, single servers, or specific protocols

---

## 🏗️ Core Concepts

### 👤 Person

A real human being.
- Has a name (e.g., "Paweł Mojski")
- Has an account in AAD / LDAP / whatever
- **Does NOT log into systems** - persons enter environments

### 🎫 Grant

Permission to be inside.
- Defines **where** (which servers/groups)
- Defines **how long** (8 hours, 1 week, permanent)
- Defines **under what conditions** (time windows, protocols, SSH logins allowed)

**A grant allows a person to be inside.**

Not:
- ❌ role
- ❌ group  
- ❌ policy document

Only a specific permission.

### 🏃 Stay

The fact of being inside.
- **Stay starts** when person enters (first connection)
- **Stay ends** when grant expires or is revoked
- **Stay is always linked** to a person and grant
- **Stay may have many sessions** (disconnect/reconnect)

Person **stays inside** even between connections.

Not:
- ❌ session
- ❌ connection
- ❌ login

### 🔌 Session

Single TCP connection within a stay.
- SSH connection (terminal)
- RDP connection (desktop)
- HTTP connection (web GUI)

Technical detail. Stay is what matters.

### 🚪 Entry

The way to get inside.
- **ssh_proxy** - Entry via SSH (port 22)
- **rdp_proxy** - Entry via RDP (port 3389)
- **http_proxy** - Entry via HTTP/HTTPS (future)

Entry checks grant, starts or joins stay.

### 🧾 Username

Technical identifier on backend systems.
- Exists on hosts (Linux accounts, DB users, etc.)
- Exists in legacy (Cisco, routers, appliances)
- **Does NOT represent a person**

**Username is an implementation detail.**

Inside maps `username → person`, but:
- ❌ Doesn't change the host
- ❌ Doesn't change the client
- ❌ Doesn't inform AAD
- ❌ Doesn't inform target

This is a key architectural point.

### 📜 Record

Audit trail.
- **Who was inside** (person)
- **When** (timestamps)
- **Based on which grant**
- **What they did** (session recordings)

Audit without auditing.

---

## 🎯 How It Works

### 1. The Gateway (Inside)

Inside runs on a single server (e.g., `gateway.company.com`):
- **Port 22** - SSH entry point
- **Port 3389** - RDP entry point
- **Port 5000** - Web management interface

### 2. Person Enters via Entry

Person tries to connect:
```bash
ssh alice@prod-db-01.company.com
```

Inside (ssh_proxy):
1. Identifies person by source IP
2. Checks if person has valid grant to target
3. If yes: Creates or joins stay, proxies connection
4. If no: Denies, records denial reason

### 3. Stay Inside

Alice is now **inside prod-db-01**:
- Can disconnect/reconnect freely (same stay)
- All sessions recorded (terminal logs)
- Visible in dashboard: "Alice is inside prod-db-01"

### 4. Stay Ends

Stay ends when:
- Grant expires (time limit reached)
- Admin revokes grant
- Schedule window closes (e.g., outside business hours)

Active sessions terminated, person can no longer enter.

---

## 🌟 Real-World Example

**Problem:** Production database issue at 9 AM. DBA needs immediate access.

**Traditional approach:**
1. Create VPN account (15 minutes)
2. Create SSH key (5 minutes)
3. Add key to prod-db (10 minutes + change ticket)
4. DBA connects (finally!)
5. Remember to revoke later (usually forgotten)

**With Inside:**
```bash
# Admin (30 seconds):
inside grant dba-john --server prod-db-01 --duration 4h

# DBA (immediate):
ssh dba-john@prod-db-01.company.com
```

- ✅ Access granted in 30 seconds
- ✅ Automatically expires in 4 hours
- ✅ Full session recording
- ✅ Audit trail: "John was inside prod-db-01 from 09:00 to 13:00"

---

## 🎨 Web Management Interface

### Dashboard

Real-time view:
- **Who is inside right now** (active stays)
- **Recent entries** (last 100 attempts)
- **Grants expiring soon**
- **Statistics** (stays today, recordings available)

Auto-refresh every 5 seconds.

### Grant Creation Wizard

Simple 4-step process:
1. **Who** - Select person (or user group)
2. **Where** - Select servers (or server group)
3. **How** - Protocol (SSH/RDP), duration, schedule
4. **Review** - Confirm and create

### Universal Search (Mega-Wyszukiwarka)

Find anything with 11+ filters:
- Person name, username
- Server, group, IP
- Protocol, status
- Date range
- Grant ID, session ID
- Denial reason

Export results to CSV. Auto-refresh every 2 seconds.

### Live Session View

Watch active SSH sessions in real-time:
- Terminal output (2-second updates)
- What person is typing right now
- Perfect for training, support, audits

### Session Recordings

Playback past sessions:
- **SSH** - Terminal player (like asciinema)
- **RDP** - MP4 video player
- Full history, searchable, exportable

---

## 💎 Features

### Access Control
- ✅ **Multiple source IPs per person** - Home, office, VPN, mobile
- ✅ **Server groups** - Grant access to entire groups ("All production servers")
- ✅ **Granular scope** - Group level, server level, or protocol level
- ✅ **Protocol filtering** - SSH only, RDP only, or both
- ✅ **SSH login restrictions** - Allow only specific system accounts (usernames)
- ✅ **Temporal grants** - Time-limited with automatic expiration
- ✅ **Schedule windows** - Access only Mon-Fri 9-17, recurring weekly
- ✅ **Recursive groups** - User groups with inheritance

### Stay Management
- ✅ **Live monitoring** - See who is inside in real-time
- ✅ **SSH live view** - Watch terminal session as it happens
- ✅ **Recording** - SSH (terminal) and RDP (video)
- ✅ **Playback** - Review past stays
- ✅ **Search** - Find stays by person, server, time, status
- ✅ **Auto-refresh** - Dashboard updates every 5s, search every 2s
- ✅ **Grant expiration** - Sessions terminated when grant ends (persons get advance warning)

### Auditing
- ✅ **Entry attempts** - Both successful and denied
- ✅ **Grant changes** - Full audit trail with history
- ✅ **Denial reasons** - Clear logging why entry was denied
- ✅ **Export** - CSV export for reporting/compliance

### User Experience
- ✅ **Transparent** - Works with standard SSH/RDP clients
- ✅ **No agents** - Zero software on client or backend
- ✅ **Native tools** - Use ssh, mstsc, PuTTY - whatever you prefer
- ✅ **Port forwarding** - SSH -L, -R, -D work (if grant allows)
- ✅ **File transfer** - scp, sftp work normally

---

## 🚀 Why Inside Is Different

### 1️⃣ Instant Mental Model

Not "access", not "identity", not "control".

Everyone immediately understands:
- Who is inside
- Who can be inside
- What they do while inside
- When they stop being inside

No need to explain architecture.

### 2️⃣ Practical Reality vs. Theoretical Ideal

This shows the practical difference between theory and real IT:

| Aspect | Inside | Traditional IAM/PAM |
|--------|--------|---------------------|
| **Deployment time** | 1 hour | Months |
| **Invasiveness** | Zero changes to clients/servers | Agents, configs everywhere |
| **User acceptance** | Users notice nothing | Programmers protest |
| **Control & audit** | Full accountability per stay | Weak session tracking |
| **Scalability** | Every new VM/server auto-protected | Per-host configuration |

💡 **Bottom line for CTO/CISO:**

*"We don't change the world - we give you full accountability and audit in real IT in 1 hour, not months."*

### 3️⃣ Identity is NOT a username

- ✅ **Identity = person**, not system account
- System accounts can be: shared, cloned, temporary
- Every stay is linked to **a specific person**

> 💡 **For auditor/CTO:** Technical account ≠ user accountability

### 4️⃣ Stay-centric access

- ⏱ **Time-limited grants** - access only in designated time
- 🔒 **No active grant → no entry**
- ❌ **Stay ends automatically when grant expires**

> 🔑 Stay control instead of fighting with system IAM

### 5️⃣ Full auditability

- 🎥 **Recording every session**
- 📝 Sessions linked to person, not account
- 🔍 Ability to review every person's actions

> 📜 **ISO 27001:** auditability and accountability satisfied

### 6️⃣ Non-invasive design

- ⚡ No agents, no PAM, no firewall changes required
- 🖥 Works with native tools (SSH, vendor CLIs)
- ♻️ Perfect for legacy systems and appliances

> 🛡 Minimal operational risk and easy deployment

### 7️⃣ Practical reality

- 🖥 VM cloned → automatically subject to Inside rules
- 👥 Shared accounts → auditable stays
- ⏳ "Temporary" machines → recorded and controlled, even years later

> 🚀 System adapted to **real IT**, not theoretical ideal

### 8️⃣ ISO 27001 alignment

- ✅ Controlled access
- ✅ Least privilege (temporal)
- ✅ Accountability & auditability
- ✅ Non-invasive deployment

> 📌 Meets **real audit requirements** without IAM revolution

### 9️⃣ Key takeaway

> **"We don't fix the world. We fix accountability.**
> **What matters is who acts, when, and what they do - not the account."**

---

## 🏗️ Architecture

### Current Architecture (v1.8)

```
Person (anywhere)
    ↓
Inside Gateway (one server)
    ├── ssh_proxy (Entry via SSH :22)
    ├── rdp_proxy (Entry via RDP :3389)
    └── web_ui (:5000)
    ↓
Backend Servers (10.0.x.x)
```

### How Entry Works

```
1. Person connects: ssh alice@prod-db-01
2. Entry (ssh_proxy) extracts:
   - Source IP (identifies person)
   - Target hostname (identifies server)
3. Database lookup:
   - Person has valid grant?
   - Grant allows SSH?
   - Grant allows this server?
   - Grant allows this SSH username?
4. If yes:
   - Create or join stay
   - Create session within stay
   - Proxy to backend
   - Record everything
5. If no:
   - Deny entry
   - Record denial reason
```

### Future Architecture (v1.9+)

**Distributed:** Tower (control plane) + Gates (data planes)

```
Tower (Control Plane)
├── Web UI
├── REST API (/api/v1/)
└── PostgreSQL (grants, stays, persons)

Gates (Data Plane - distributed)
├── Gate 1 (DMZ) - ssh/rdp/http entries
├── Gate 2 (Cloud) - ssh/rdp entries
└── Gate 3 (Office) - ssh entry only

Communication: REST API + local cache
```

Benefits:
- Scale horizontally (add more Gates)
- Geographic distribution
- Offline mode (Gates cache grants)
- Reduce blast radius

---

## 📋 Use Cases

### 1. Contractor Access

**Problem:** External contractor needs 2 weeks access to staging environment.

**Solution:**
```bash
inside grant contractor-bob --group staging-servers --duration 14d
```

After 14 days: automatic expiration, no cleanup needed.

### 2. On-Call Rotation

**Problem:** Weekly on-call engineer needs emergency production access.

**Solution:**
```bash
# Every Monday, grant current on-call person
inside grant oncall-engineer --group production \\
  --schedule "Mon-Sun 00:00-23:59" \\
  --duration 7d
```

Grant automatically expires, new on-call gets new grant.

### 3. Temporary Privilege Escalation

**Problem:** Junior admin needs sudo for specific 1-hour maintenance window.

**Solution:**
```bash
inside grant junior-admin --server app-01 \\
  --ssh-login root \\
  --duration 1h
```

After 1 hour: root access revoked automatically, stay ends.

### 4. Compliance Audit

**Problem:** "Show me everyone who was inside production last month."

**Solution:**
- Web UI → Search
- Filter: server_group="Production", date_from="2025-12-01"
- Export → CSV
- Done. Full audit trail with session recordings.

---

## 🔐 Security

### Authentication

- **Person identification** - By source IP (mapped to person in database)
- **No passwords** - Inside never handles passwords
- **Backend authentication** - SSH keys, RDP credentials stored per person

### Authorization

- **Grant-based** - Every entry checked against active grants
- **Temporal** - Grants expire automatically
- **Granular** - Per-person, per-server, per-protocol, per-username

### Audit Trail

- **Immutable records** - All entries logged (success + denial)
- **Session recordings** - Terminal logs (SSH), video (RDP)
- **Change history** - Grant creation/modification/deletion tracked

### Session Control

- **Live monitoring** - See who is inside right now
- **Forced termination** - Admin can kill active stays
- **Auto-termination** - Stay ends when grant expires (with warnings)

---

## 🛠️ Advanced Features

### Port Forwarding Control

Control who can do SSH port forwarding:

```bash
# Grant with port forwarding allowed
inside grant alice --server bastion \\
  --allow-port-forwarding local,remote,dynamic

# Grant without port forwarding
inside grant bob --server app-server \\
  --no-port-forwarding
```

### Schedule-Based Access

Access only during business hours:

```bash
inside grant alice --server prod-db \\
  --schedule "Mon-Fri 09:00-17:00" \\
  --timezone "Europe/Warsaw"
```

Recurring weekly - person can enter anytime within schedule, automatically blocked outside.

### TPROXY Mode (v1.9)

Transparent proxy for Linux routers:

```bash
# Person connects directly to server IP
ssh 10.50.1.100

# iptables redirects to Inside
iptables -t mangle -A PREROUTING -p tcp --dport 22 \\
  -j TPROXY --on-port 2222

# Inside extracts real destination (SO_ORIGINAL_DST)
# Person doesn't know Inside exists
```

Perfect for Tailscale exit nodes, VPN concentrators.

### HTTP/HTTPS Proxy (v2.1 - Future)

For legacy network devices (old switches, routers, appliances):

```bash
# Grant access to switch web GUI
inside grant network-admin --server old-cisco-switch \\
  --protocol http --duration 2h

# Person uses browser with proxy
https_proxy=gateway:8080 firefox
```

MITM for full HTTPS control, session recording for web GUIs.

---

## 📊 Monitoring & Operations

### System Health

- PostgreSQL status
- Proxy processes (ssh_proxy, rdp_proxy)
- Recording storage usage
- Active stays count

### Metrics

- Entries per hour (successful / denied)
- Average stay duration
- Most accessed servers
- Recording conversion queue

### Alerts

- Grant expiring soon (< 1 hour)
- Recording storage > 80%
- Failed entry spike
- Backend server unreachable

---

## 🗓️ Roadmap

### Current: v1.8 (Mega-Wyszukiwarka) ✅

- Universal search with 11+ filters
- Auto-refresh dashboard
- CSV export
- Full audit trail

### Next: v1.9 (Distributed + TPROXY) 🎯

- Tower/Gate architecture (distributed)
- TPROXY transparent proxy
- API layer (REST)
- GUI improvements

### Future: v2.0 (CLI Tools) 💡

- curl-based CLI (`inside grant`, `inside stays`)
- Token authentication
- Bash completion

### Future: v2.1 (HTTP Proxy) 🔮

- HTTP/HTTPS proxy for legacy devices
- MITM for web GUIs (old switches, routers)
- Policy-based web access control

---

## 📚 Quick Start

### Prerequisites

- Linux server (Debian 12 recommended)
- PostgreSQL 15+
- Python 3.13+
- Public IP or VPN access for clients

### Installation

```bash
# 1. Clone repository
git clone https://github.com/pawelmojski/inside.git
cd inside

# 2. Install dependencies
pip install -r requirements.txt

# 3. Setup database
sudo -u postgres createdb inside
alembic upgrade head

# 4. Configure
cp config/inside.conf.example config/inside.conf
vim config/inside.conf

# 5. Start services
sudo systemctl start inside-ssh-proxy
sudo systemctl start inside-rdp-proxy
sudo systemctl start inside-flask
```

### First Grant

```bash
# 1. Add person
inside person add "John Doe" --ip 100.64.0.50

# 2. Add backend server
inside server add prod-db-01 --ip 10.0.1.100

# 3. Create grant
inside grant create john.doe --server prod-db-01 --duration 8h

# 4. Person can now enter
ssh john.doe@gateway.company.com
```

---

## 🎓 Documentation

- **[ROADMAP.md](ROADMAP.md)** - Feature roadmap and version history
- **[DOCUMENTATION.md](DOCUMENTATION.md)** - Technical documentation
- **[README_PL.md](README_PL.md)** - Polish version

---

## 💬 TL;DR

**Inside in one sentence:**

*Time-limited grants for real people to be inside infrastructure, with full audit and session recording, deployed in 1 hour.*

**Key differences:**

- 👤 **Person ≠ username** - Accountability for humans, not accounts
- ⏱ **Stay-centric** - Who is inside right now, for how long
- 🎫 **Grant-based** - Specific permission, not role/group
- 🚀 **Non-invasive** - No agents, no changes, 1 hour deployment
- 📜 **Full audit** - Every entry, every stay, every session recorded

**One command to grant access:**
```bash
inside grant alice --server prod-db --duration 8h
```

**One place to see everything:**
```
Dashboard → Who is inside right now
```

---

**Project:** Inside
**Repository:** https://github.com/pawelmojski/inside
**Status:** Production (v1.8)
**License:** Commercial (monetization options open)

# Jumphost Web Management Interface

**Flask-based web GUI for SSH/RDP jumphost management**

Version: 1.1  
Release Date: January 4, 2026  
Status: Production Ready

---

## Overview

The Jumphost Web GUI provides a modern, user-friendly interface for managing all aspects of the SSH/RDP jumphost infrastructure. Built with Flask and Bootstrap 5, it offers complete CRUD operations for users, servers, groups, and access policies, along with real-time monitoring and audit logging.

### Key Features

- 📊 **Dashboard** - Service status, statistics, and recent activity
- 👥 **User Management** - CRUD operations with multiple source IPs
- 🖥️ **Server Management** - CRUD with automatic IP allocation
- 📁 **Group Management** - Server grouping with N:M relationships
- 🔑 **Policy Wizard** - Flexible access grant system
- 📈 **Monitoring** - Audit logs and connection charts
- 🔐 **Authentication** - Placeholder ready for Azure AD integration

---

## Architecture

### Technology Stack

#### Backend
- **Flask 3.1.2** - Web framework
- **Flask-Login 0.6.3** - Session management
- **Flask-WTF 1.2.2** - Form handling with CSRF protection
- **Flask-Cors 6.0.2** - API endpoint support
- **SQLAlchemy** - ORM for database access
- **PostgreSQL 17** - Database backend
- **psutil 7.2.1** - System monitoring

#### Frontend
- **Bootstrap 5.3.0** - CSS framework (CDN)
- **Bootstrap Icons 1.11.0** - Icon library (CDN)
- **Chart.js 4.4.0** - Statistics visualization (CDN)
- **Custom CSS** - Service status indicators, stats cards
- **Custom JavaScript** - AJAX updates, Chart.js integration

### Application Structure

```
/opt/jumphost/src/web/
├── app.py                          # Main Flask application
├── blueprints/                     # Modular route handlers
│   ├── __init__.py
│   ├── auth.py                     # Authentication (login/logout)
│   ├── dashboard.py                # Dashboard with monitoring
│   ├── users.py                    # User CRUD operations
│   ├── servers.py                  # Server CRUD operations
│   ├── groups.py                   # Group CRUD operations
│   ├── policies.py                 # Policy grant/revoke wizard
│   └── monitoring.py               # Audit logs and charts
├── templates/                      # Jinja2 HTML templates
│   ├── base.html                   # Base layout with navbar
│   ├── dashboard/
│   │   └── index.html              # Dashboard page
│   ├── users/
│   │   ├── index.html              # User list
│   │   ├── view.html               # User details
│   │   ├── add.html                # Add user form
│   │   └── edit.html               # Edit user form
│   ├── servers/
│   │   ├── index.html              # Server list
│   │   ├── view.html               # Server details
│   │   ├── add.html                # Add server form
│   │   └── edit.html               # Edit server form
│   ├── groups/
│   │   ├── index.html              # Group list
│   │   ├── view.html               # Group details
│   │   ├── add.html                # Add group form
│   │   └── edit.html               # Edit group form
│   ├── policies/
│   │   ├── index.html              # Policy list
│   │   └── add.html                # Grant access wizard
│   ├── monitoring/
│   │   ├── index.html              # Charts page
│   │   └── audit.html              # Audit log viewer
│   ├── auth/
│   │   └── login.html              # Login page
│   └── errors/
│       ├── 404.html                # Not found error
│       └── 500.html                # Server error
└── static/                         # Static assets
    ├── css/
    │   └── style.css               # Custom styles (185 lines)
    └── js/
        └── app.js                  # Custom JavaScript (215 lines)
```

### Blueprint Architecture

Each blueprint is a self-contained module handling specific functionality:

| Blueprint | URL Prefix | Routes | Description |
|-----------|------------|--------|-------------|
| `auth` | `/auth` | 2 | Login and logout |
| `dashboard` | `/` | 2 | Dashboard and stats API |
| `users` | `/users` | 8 | User CRUD + source IP management |
| `servers` | `/servers` | 5 | Server CRUD |
| `groups` | `/groups` | 7 | Group CRUD + member management |
| `policies` | `/policies` | 5 | Policy CRUD + grant wizard + API |
| `monitoring` | `/monitoring` | 4 | Audit logs + chart APIs |

**Total**: 7 blueprints, 33 routes

---

## Features Documentation

### 1. Dashboard

**Route**: `/` (GET)

#### Service Status
Monitors critical services with real-time status indicators:
- **SSH Proxy** - Port 22, checks `pgrep -f ssh_proxy`
- **RDP Proxy** - Port 3389, checks `pgrep -f pyrdp-mitm`
- **PostgreSQL** - Port 5432, checks `systemctl is-active postgresql`

Status indicators:
- 🟢 **Running** - Green pulsing dot with uptime
- 🔴 **Stopped** - Red dot

#### Statistics Cards
- **Total Users** - Count of all users
- **Total Servers** - Count of all servers
- **Active Policies** - Count of non-expired policies
- **Today's Connections** - Count of today's audit logs

#### Today's Activity
- **Granted** - Count of access_granted actions today
- **Denied** - Count of access_denied actions today
- **Success Rate** - Percentage calculation

#### Active Sessions (NEW in v1.1) ⭐
Real-time display of currently active SSH/RDP sessions from database:
- **Protocol** - SSH (blue badge) or RDP (green badge)
- **User** - Jumphost username
- **Server** - For SSH: `ssh_username@servername (subsystem)`, for RDP: just server name
- **Backend IP** - Target server IP address (monospace format)
- **Source IP** - Client source IP (monospace format)
- **SSH Agent** - ✓ (green) if agent forwarding used, ✗ (red) if not, - (gray) for RDP
- **Started** - Relative timestamp (e.g., "2 minutes ago")

Shows last 5 active sessions, automatically updates when sessions start/end.

Example display for SSH with SFTP:
```
Protocol: SSH
User: john
Server: root@webserver1 (sftp)
Backend IP: 192.168.1.10
Source IP: 100.64.0.39
SSH Agent: ✓
Started: 3 minutes ago
```

Example display for RDP:
```
Protocol: RDP
User: alice
Server: winserver1
Backend IP: 10.30.0.140
Source IP: 100.64.0.39
SSH Agent: -
Started: 5 minutes ago
```

**Technical Details:**
- Sessions are tracked in real-time using database `sessions` table
- SSH: Session created on backend auth, closed on channel close
- RDP: Session created on access granted, closed on TCP disconnect (observer pattern)
- RDP multiplexing: Multiple TCP connections within 10s share same session
- Duration calculated on session close
- Recording paths and sizes stored automatically

#### Recent Audit Log
Last 10 audit log entries with color coding:
- 🟢 Green border - access_granted
- 🔴 Red border - access_denied
- ⚪ Gray border - other actions

#### Auto-Refresh
Stats refresh every 30 seconds via AJAX call to `/dashboard/api/stats`

---

### 2. User Management

#### User List (`/users/`)
- Table with all users
- Columns: ID, Username, Email, Source IPs count, Active policies count, Status, Created date
- Actions: View, Edit, Delete buttons
- **Add User** button in header

#### View User (`/users/view/<id>`)
- User information table
- Source IP management:
  - List of all source IPs with descriptions
  - Add IP button (modal dialog)
  - Toggle active/inactive per IP
  - Delete IP button
- Associated access policies table

#### Add User (`/users/add`)
Form fields:
- **Username** (required) - Jumphost username
- **Email** (optional) - Email for notifications
- **Is Active** (checkbox, default: checked)
- **Source IPs** (dynamic fields):
  - IP Address (required)
  - Description (optional)
  - **Add Another IP** button for multiple IPs

#### Edit User (`/users/edit/<id>`)
Form fields:
- **Username** (required)
- **Email** (optional)
- **Is Active** (checkbox)
- Note: Source IPs managed via View page

---

### 3. Server Management

#### Server List (`/servers/`)
- Table with all servers
- Columns: ID, Name, Address:Port, Proxy IP, Protocols, Groups count, Status, Created date
- Actions: View, Edit, Delete buttons
- **Add Server** button in header

#### View Server (`/servers/view/<id>`)
- Server information table
- IP Allocation details:
  - Proxy IP (if allocated)
  - NAT Port SSH
  - NAT Port RDP
  - Allocated timestamp
- Group Memberships table (list of groups containing this server)

#### Add Server (`/servers/add`)
Form fields:
- **Name** (required) - Friendly server name
- **Address** (required) - IP address or hostname
- **Port** (required, default: 22) - Primary port
- **Description** (optional)
- **SSH Enabled** (checkbox, default: checked)
- **RDP Enabled** (checkbox)
- **Allocate IP** (checkbox, default: checked) - Auto-allocate proxy IP from pool
- **Is Active** (checkbox, default: checked)

#### Edit Server (`/servers/edit/<id>`)
Form fields:
- **Name** (required)
- **Address** (required)
- **Port** (required)
- **Description** (optional)
- **SSH Enabled** (checkbox)
- **RDP Enabled** (checkbox)
- **Is Active** (checkbox)

---

### 4. Group Management

#### Group List (`/groups/`)
- Table with all groups
- Columns: ID, Name, Description, Server count, Created date
- Actions: View, Edit, Delete buttons
- **Add Group** button in header

#### View Group (`/groups/view/<id>`)
- Group information table
- Group Members section:
  - Table of servers in this group
  - Columns: Server name, Address:Port, Protocols, Status
  - Remove from group button per server
  - **Add Server** button (modal) - shows available servers not in group

#### Add Group (`/groups/add`)
Form fields:
- **Name** (required) - Unique group name
- **Description** (optional)
- Note: Servers added after group creation

#### Edit Group (`/groups/edit/<id>`)
Form fields:
- **Name** (required)
- **Description** (optional)
- Note: Members managed via View page

---

### 5. Policy Management

#### Policy List (`/policies/`)
- Table with all access policies
- Columns: ID, User, Scope, Protocol, Source IP, Start time, End time, Status
- Actions: Revoke, Delete buttons
- **Grant Access** button in header

**Filters**:
- **User** dropdown - Filter by specific user
- **Show inactive** checkbox - Include revoked/expired policies
- **Apply Filters** button

#### Grant Access Wizard (`/policies/add`)

Multi-step form for granting access:

**Step 1: Select User**
- **User** dropdown (required) - Select user
- **Source IP** dropdown - Loads dynamically via AJAX
  - Options: "ANY (all source IPs)" or specific IPs
  - API: `/policies/api/user/<id>/ips`

**Step 2: Select Scope**
- **Scope Type** dropdown (required):
  - **Group** - All servers in a group
  - **Server** - Single server (all protocols)
  - **Service** - Single server + specific protocol
- **Server Group** dropdown (shown if scope=group)
- **Server** dropdown (shown if scope=server or service)
- **Protocol** dropdown (shown if scope=service):
  - Options: ALL, SSH only, RDP only

**Step 3: SSH Configuration (Optional)**
- **Allowed SSH Logins** - Comma-separated list of system accounts
  - Example: `root,admin,ubuntu`
  - Empty = no restrictions

**Step 4: Time Configuration**
- **Start Time** datetime picker (optional, default: now)
- **Duration (hours)** number input (optional, default: permanent)
  - System calculates end_time = start_time + duration

**Dynamic Behavior**:
- Scope fields show/hide based on selection
- Source IP dropdown loads via AJAX when user selected
- Form validates all required fields

---

### 6. Monitoring

#### Monitoring Dashboard (`/monitoring/`)

**Connections Last 24 Hours** (Line Chart)
- X-axis: Hours (0-23)
- Y-axis: Connection count
- Data: Hourly grouped connections from last 24 hours
- API: `/monitoring/api/stats/hourly`

**Top Users (Last 7 Days)** (Bar Chart)
- X-axis: Usernames
- Y-axis: Connection count
- Data: Top 10 users by connections in last 7 days
- API: `/monitoring/api/stats/by_user`

Charts use Chart.js and update on page load.

#### Audit Log Viewer (`/monitoring/audit`)

**Filters**:
- **Action** dropdown - Filter by action type (granted/denied/closed)
- **User** dropdown - Filter by specific user
- **Date From** date picker - Filter from date
- **Apply Filters** button

**Table**:
- Columns: Timestamp, Action (badge), User, Server, Protocol, Source IP, Details
- **50 entries per page**
- Pagination controls at bottom

**Pagination**:
- Previous/Next buttons
- Page numbers (with ellipsis for large ranges)
- Current page highlighted

---

### 7. Authentication

#### Login (`/auth/login`)

**Placeholder Authentication**:
- Username: `admin`
- Password: `admin`
- Creates/finds user in database
- Uses Flask-Login for session management

**Form**:
- Username field with icon
- Password field with icon
- Sign In button
- Hint text: "Use admin/admin for testing"

**Behavior**:
- If already authenticated → redirect to dashboard
- On success → flash message, redirect to dashboard
- On failure → flash error message

**Future**: Replace with Azure AD OAuth flow

#### Logout (`/auth/logout`)
- Clears Flask-Login session
- Flash info message
- Redirects to login page

---

## API Endpoints

### Dashboard Stats API

**GET** `/dashboard/api/stats`

Returns JSON with current statistics:

```json
{
  "total_users": 5,
  "total_servers": 10,
  "active_policies": 12,
  "today_connections": 45,
  "granted_today": 42,
  "denied_today": 3,
  "success_rate": 93.33
}
```

Used by dashboard for auto-refresh every 30 seconds.

### User Source IPs API

**GET** `/policies/api/user/<user_id>/ips`

Returns JSON with user's source IPs:

```json
{
  "ips": [
    {
      "id": 1,
      "source_ip": "100.64.0.20",
      "description": "Home network"
    },
    {
      "id": 2,
      "source_ip": "10.30.14.3",
      "description": "Office"
    }
  ]
}
```

Used by policy grant wizard for dynamic dropdown.

### Hourly Stats API

**GET** `/monitoring/api/stats/hourly`

Returns JSON with connections per hour (last 24 hours):

```json
{
  "labels": ["00:00", "01:00", ..., "23:00"],
  "data": [5, 3, 1, 0, 0, 2, 8, 15, ...]
}
```

Used by monitoring charts.

### Top Users API

**GET** `/monitoring/api/stats/by_user`

Returns JSON with top 10 users (last 7 days):

```json
{
  "labels": ["p.mojski", "j.doe", ...],
  "data": [125, 87, ...]
}
```

Used by monitoring charts.

---

## Deployment

### Development Mode

```bash
cd /opt/jumphost/src/web
/opt/jumphost/venv/bin/python3 app.py
```

- Binds to: `0.0.0.0:5000`
- Debug mode: ON
- Auto-reload: ON
- Use for: Development and testing

### Production Mode (gunicorn)

```bash
cd /opt/jumphost/src/web
/opt/jumphost/venv/bin/gunicorn \
  --bind 0.0.0.0:5000 \
  --workers 4 \
  --access-logfile /var/log/jumphost/web-access.log \
  --error-logfile /var/log/jumphost/web-error.log \
  app:app
```

- Workers: 4 (adjust based on CPU cores)
- Logging: Separate access and error logs
- Use for: Production deployment

### Systemd Service

Create `/etc/systemd/system/jumphost-web.service`:

```ini
[Unit]
Description=Jumphost Web GUI
After=network.target postgresql.service

[Service]
Type=notify
User=www-data
Group=www-data
WorkingDirectory=/opt/jumphost/src/web
Environment="PATH=/opt/jumphost/venv/bin"
ExecStart=/opt/jumphost/venv/bin/gunicorn \
  --bind 0.0.0.0:5000 \
  --workers 4 \
  --access-logfile /var/log/jumphost/web-access.log \
  --error-logfile /var/log/jumphost/web-error.log \
  app:app
Restart=always

[Install]
WantedBy=multi-user.target
```

Enable and start:
```bash
sudo systemctl daemon-reload
sudo systemctl enable jumphost-web
sudo systemctl start jumphost-web
```

### Nginx Reverse Proxy

Create `/etc/nginx/sites-available/jumphost`:

```nginx
server {
    listen 80;
    server_name jumphost.local 10.0.160.5;

    location / {
        proxy_pass http://localhost:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location /static/ {
        alias /opt/jumphost/src/web/static/;
        expires 30d;
    }
}
```

Enable and reload:
```bash
sudo ln -s /etc/nginx/sites-available/jumphost /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

---

## Security

### Current Implementation

- **CSRF Protection**: Flask-WTF on all forms
- **Session Security**: HTTPOnly cookies
- **SQL Injection**: SQLAlchemy ORM prevents injection
- **XSS Prevention**: Jinja2 autoescaping
- **Login Required**: All routes except login decorated with `@login_required`
- **Flash Messages**: User feedback for all operations

### Planned Enhancements

- **Azure AD Integration**: OAuth 2.0 authentication
- **RBAC**: Role-based access control (admin vs readonly)
- **Rate Limiting**: Prevent brute force attacks
- **SSL/TLS**: HTTPS with Let's Encrypt
- **Audit Logging**: Log all web GUI actions
- **Session Timeout**: Configurable session expiration
- **Password Policies**: If using local auth

---

## Troubleshooting

### Flask Won't Start

```bash
# Check if port 5000 is in use
ss -tlnp | grep 5000

# Kill existing Flask processes
pkill -f "python.*app.py"

# Check logs
tail -f /tmp/flask.log
```

### Database Connection Error

```bash
# Verify PostgreSQL is running
systemctl status postgresql

# Check database credentials in .env
cat /opt/jumphost/.env | grep DATABASE_URL

# Test connection
psql -U jumphost_user -d jumphost -h localhost
```

### Import Errors

```bash
# Verify virtual environment
source /opt/jumphost/venv/bin/activate
pip list | grep Flask

# Reinstall dependencies
pip install -r /opt/jumphost/requirements.txt
```

### Login Not Working

- Verify User model has UserMixin
- Check Flask-Login session configuration
- Clear browser cookies
- Check database for admin user:
  ```sql
  SELECT * FROM users WHERE username = 'admin';
  ```

### Chart.js Not Loading

- Check CDN connectivity
- Verify Chart.js version (4.4.0)
- Check browser console for errors
- Verify API endpoints return data

---

## Future Enhancements

### Phase 1: Authentication
- [ ] Azure AD OAuth integration
- [ ] AAD Security Group mapping to server_groups
- [ ] User profile page with AAD info
- [ ] Logout redirects to AAD logout

### Phase 2: Features
- [ ] Session recording playback viewer
  - Asciinema player for SSH sessions
  - PyRDP player for RDP sessions
- [ ] Real-time session monitoring
  - WebSocket for live updates
  - Kill session button
- [ ] Bulk operations
  - Mass grant/revoke policies
  - Bulk user import (CSV)
- [ ] Email notifications
  - Access granted/revoked
  - Policy expiration warnings

### Phase 3: Advanced
- [ ] REST API with Swagger docs
- [ ] Multi-tenancy support
- [ ] Advanced audit log search
- [ ] Export functionality (CSV, JSON, PDF)
- [ ] User activity dashboard
- [ ] Prometheus metrics endpoint

---

## Statistics

- **Total Files**: 32
- **Python Code**: ~1,050 lines (blueprints + app.py)
- **HTML Templates**: ~2,200 lines (25 files)
- **CSS**: ~185 lines
- **JavaScript**: ~215 lines
- **Total Lines**: ~3,650 lines
- **Development Time**: 1 day
- **Routes**: 33
- **Templates**: 25
- **API Endpoints**: 4

---

## Credits

**Author**: Piotr Mojski  
**Framework**: Flask 3.1.2  
**Frontend**: Bootstrap 5.3.0  
**Charts**: Chart.js 4.4.0  
**Icons**: Bootstrap Icons 1.11.0  

---

## License

Proprietary - Internal use only


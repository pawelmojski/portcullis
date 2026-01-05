# JumpHost Installation Guide

Complete installation instructions for JumpHost v1.3 with MP4 conversion support.

## Prerequisites

- **OS**: Debian 13 (or similar)
- **Python**: 3.13+
- **PostgreSQL**: 17+
- **RAM**: 4GB minimum (8GB recommended for MP4 conversion)
- **Disk**: 35GB+ (for session recordings)
- **CPU**: Host CPU passthrough recommended (for Qt/PySide6)

## System Requirements

### CPU Requirements (Important!)

For MP4 conversion (PySide6/Qt), CPU must support:
- `ssse3` (Supplemental SSE3)
- `sse4_1` (SSE4.1)
- `sse4_2` (SSE4.2)
- `popcnt` (Population Count)

#### Proxmox VM Configuration

Edit VM config or use GUI:

```bash
# Option 1: Host CPU passthrough (recommended)
cpu: host

# Option 2: Specific flags
cpu: kvm64,flags=+ssse3;+sse4.1;+sse4.2;+popcnt
```

Verify CPU features:
```bash
grep -E "ssse3|sse4_1|sse4_2|popcnt" /proc/cpuinfo | head -1
```

If these flags are missing, MP4 conversion will fail with segmentation fault.

---

## Step 1: Install System Dependencies

```bash
# Update system
sudo apt-get update && sudo apt-get upgrade -y

# Install build essentials
sudo apt-get install -y \
    build-essential \
    python3-dev \
    python3-venv \
    git

# Install PostgreSQL
sudo apt-get install -y \
    postgresql \
    postgresql-contrib \
    libpq-dev

# Install Qt dependencies (required for PySide6/MP4 conversion)
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

# Optional: QEMU guest agent (if VM)
sudo apt-get install -y qemu-guest-agent
```

---

## Step 2: Clone Repository

```bash
sudo mkdir -p /opt/jumphost
sudo chown $USER:$USER /opt/jumphost
cd /opt/jumphost
git clone <repository_url> .
```

Or if already cloned:
```bash
cd /opt/jumphost
git pull origin master
git checkout v1.3
```

---

## Step 3: Setup PostgreSQL Database

```bash
# Create database and user
sudo -u postgres psql << EOF
CREATE DATABASE jumphost;
CREATE USER jumphost WITH PASSWORD 'your_secure_password';
GRANT ALL PRIVILEGES ON DATABASE jumphost TO jumphost;
\c jumphost
GRANT ALL ON SCHEMA public TO jumphost;
ALTER DATABASE jumphost OWNER TO jumphost;
EOF
```

Update database configuration:
```bash
# Edit connection string
export DATABASE_URL="postgresql://jumphost:your_secure_password@localhost/jumphost"
# Or add to .env file
echo "DATABASE_URL=postgresql://jumphost:your_secure_password@localhost/jumphost" > /opt/jumphost/.env
```

---

## Step 4: Create Python Virtual Environments

### 4.1 Main Application Environment

```bash
cd /opt/jumphost
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

If `requirements.txt` doesn't exist:
```bash
pip install Flask Flask-Login Flask-WTF Flask-Cors gunicorn \
    SQLAlchemy alembic psycopg2-binary \
    paramiko pyrdp-mitm \
    typer rich \
    python-dateutil pytz psutil
```

### 4.2 MP4 Converter Environment (Separate)

**Important**: This must be a separate environment due to PySide6 dependency conflicts.

```bash
cd /opt/jumphost
python3 -m venv venv-pyrdp-converter
source venv-pyrdp-converter/bin/activate
pip install --upgrade pip
pip install -r requirements-pyrdp-converter.txt
```

If `requirements-pyrdp-converter.txt` doesn't exist:
```bash
pip install PySide6 av pyrdp-mitm qimage2ndarray
```

**Test PySide6 installation**:
```bash
python3 -c "from PySide6 import QtCore; print('PySide6 OK')"
```

If you get a segmentation fault, check CPU features (see Prerequisites).

---

## Step 5: Apply PyRDP Patches

**Critical**: PyRDP requires patches in BOTH environments!

### 5.1 Main Venv Patches (Access Control Integration)

See [PYRDP_PATCHES_MAIN_VENV.md](PYRDP_PATCHES_MAIN_VENV.md) for detailed instructions.

```bash
cd /opt/jumphost
source venv/bin/activate

# Backup original files
cp venv/lib/python3.13/site-packages/pyrdp/core/mitm.py{,.orig}
cp venv/lib/python3.13/site-packages/pyrdp/enum/rdp.py{,.orig}
cp venv/lib/python3.13/site-packages/pyrdp/mitm/FileMapping.py{,.orig}

# Apply patches (automated)
patch -p0 < patches/pyrdp_core_mitm.patch
patch -p0 < patches/pyrdp_enum_rdp.patch
patch -p0 < patches/pyrdp_mitm_filemapping.patch
```

**Manual patching** (if automated fails):
- Edit `core/mitm.py` - Add access control hooks to `buildProtocol()`
- Edit `enum/rdp.py` - Add `RDP10_12` and `_missing_()` method
- Edit `mitm/FileMapping.py` - Change `from typing import io` to `BinaryIO`

Verify main venv patches:
```bash
grep "JUMPHOST_ENABLED" venv/lib/python3.13/site-packages/pyrdp/core/mitm.py
grep "RDP10_12" venv/lib/python3.13/site-packages/pyrdp/enum/rdp.py
grep "BinaryIO" venv/lib/python3.13/site-packages/pyrdp/mitm/FileMapping.py
```

### 5.2 Converter Venv Patches (MP4 Conversion)

### 5.2 Converter Venv Patches (MP4 Conversion)

See [PYRDP_PATCHES.md](PYRDP_PATCHES.md) for detailed instructions.

```bash
cd /opt/jumphost
source venv-pyrdp-converter/bin/activate

# Backup original files
cp venv-pyrdp-converter/lib/python3.13/site-packages/pyrdp/enum/rdp.py{,.orig}
cp venv-pyrdp-converter/lib/python3.13/site-packages/pyrdp/mitm/FileMapping.py{,.orig}
cp venv-pyrdp-converter/lib/python3.13/site-packages/pyrdp/convert/utils.py{,.orig}

# Edit files manually (see PYRDP_PATCHES.md for exact changes)
# 1. Add RDP10_12 and _missing_() to enum/rdp.py
# 2. Change 'from typing import io' to 'from typing import BinaryIO' in mitm/FileMapping.py
# 3. Add 'fps=10' parameter in convert/utils.py
```

Verify converter venv patches:
```bash
grep "RDP10_12" venv-pyrdp-converter/lib/python3.13/site-packages/pyrdp/enum/rdp.py
grep "BinaryIO" venv-pyrdp-converter/lib/python3.13/site-packages/pyrdp/mitm/FileMapping.py
grep "fps=10" venv-pyrdp-converter/lib/python3.13/site-packages/pyrdp/convert/utils.py
```

All three commands should return results.

---

## Step 6: Database Migration

```bash
cd /opt/jumphost
source venv/bin/activate

# Run migrations
alembic upgrade head

# Verify tables exist
python3 << EOF
from src.core.database import SessionLocal, engine, Base
from sqlalchemy import inspect
inspector = inspect(engine)
tables = inspector.get_table_names()
print(f"Tables created: {len(tables)}")
print(tables)
EOF
```

Expected tables: users, servers, server_groups, access_policies, sessions, mp4_conversion_queue, audit_logs, etc.

---

## Step 7: Create Required Directories

```bash
sudo mkdir -p /var/log/jumphost/{ssh_recordings,rdp_recordings/{replays,files,certs,json_cache,mp4_cache}}
sudo mkdir -p /opt/jumphost/{logs,certs,config}

# Set permissions
sudo chown -R $USER:$USER /var/log/jumphost
sudo chown -R $USER:$USER /opt/jumphost

# MP4 cache should be writable by root (workers run as root)
sudo chown -R root:root /var/log/jumphost/rdp_recordings/mp4_cache
sudo chmod 755 /var/log/jumphost/rdp_recordings/mp4_cache
```

---

## Step 8: Generate SSH Host Key

```bash
cd /opt/jumphost
ssh-keygen -t rsa -b 4096 -f ssh_host_key -N ""
chmod 600 ssh_host_key
```

---

## Step 9: Setup Systemd Services

### 9.1 Flask Web Service

```bash
sudo cp /opt/jumphost/deployment/systemd/jumphost-flask.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable jumphost-flask.service
```

### 9.2 SSH Proxy Service

```bash
sudo cp /opt/jumphost/deployment/systemd/jumphost-ssh-proxy.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable jumphost-ssh-proxy.service
```

### 9.3 RDP Proxy Service

```bash
sudo cp /opt/jumphost/deployment/systemd/jumphost-rdp-proxy.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable jumphost-rdp-proxy.service
```

### 9.4 MP4 Converter Workers

```bash
sudo cp /opt/jumphost/deployment/systemd/jumphost-mp4-converter@.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable jumphost-mp4-converter@1.service
sudo systemctl enable jumphost-mp4-converter@2.service
```

---

## Step 10: Configure Logrotate

```bash
sudo cp /opt/jumphost/deployment/logrotate/jumphost /etc/logrotate.d/
sudo chmod 644 /etc/logrotate.d/jumphost
```

---

## Step 11: Create Admin User (Optional)

```bash
cd /opt/jumphost
source venv/bin/activate

python3 << EOF
from src.core.database import SessionLocal, User
from werkzeug.security import generate_password_hash

db = SessionLocal()
admin = User(
    username="admin",
    email="admin@jumphost.local",
    password_hash=generate_password_hash("admin"),  # Change this!
    is_admin=True
)
db.add(admin)
db.commit()
print("Admin user created: admin/admin")
EOF
```

**Important**: Change the default password immediately after first login!

---

## Step 12: Start Services

```bash
# Start all services
sudo systemctl start jumphost-flask.service
sudo systemctl start jumphost-ssh-proxy.service
sudo systemctl start jumphost-rdp-proxy.service
sudo systemctl start jumphost-mp4-converter@1.service
sudo systemctl start jumphost-mp4-converter@2.service

# Check status
sudo systemctl status jumphost-flask.service
sudo systemctl status jumphost-ssh-proxy.service
sudo systemctl status jumphost-rdp-proxy.service
sudo systemctl status jumphost-mp4-converter@1.service
sudo systemctl status jumphost-mp4-converter@2.service
```

---

## Step 13: Verify Installation

### 13.1 Check Web Interface

```bash
curl http://localhost:5000
```

Access: `http://<server-ip>:5000`  
Login: `admin` / `admin`

### 13.2 Check Logs

```bash
tail -f /var/log/jumphost/flask.log
tail -f /var/log/jumphost/ssh_proxy.log
tail -f /var/log/jumphost/rdp_mitm.log
tail -f /var/log/jumphost/mp4-converter-worker1.log
tail -f /var/log/jumphost/mp4-converter-worker2.log
```

### 13.3 Test MP4 Conversion

```bash
# Create test recording (if you have one)
source /opt/jumphost/venv-pyrdp-converter/bin/activate
pyrdp-convert -f mp4 -o /tmp/test.mp4 /var/log/jumphost/rdp_recordings/replays/your_recording.pyrdp

# Should complete without errors
# Check output
ls -lh /tmp/test.mp4
```

---

## Troubleshooting

### PySide6 Segmentation Fault

**Cause**: CPU doesn't support required instructions (ssse3, sse4.1, sse4.2, popcnt)

**Solution**: 
1. Check Proxmox VM CPU settings
2. Change to `cpu: host` or add required flags
3. Restart VM
4. Verify: `grep -E "ssse3|sse4" /proc/cpuinfo`

### MP4 Conversion Fails

**Cause**: PyRDP patches not applied

**Solution**: Follow [PYRDP_PATCHES.md](PYRDP_PATCHES.md) exactly

### Service Won't Start

```bash
# Check logs
journalctl -u jumphost-flask.service -f
journalctl -u jumphost-mp4-converter@1.service -f

# Check permissions
ls -la /opt/jumphost/
ls -la /var/log/jumphost/
```

### Database Connection Error

```bash
# Check PostgreSQL is running
sudo systemctl status postgresql

# Test connection
psql -U jumphost -d jumphost -h localhost

# Verify DATABASE_URL in .env
cat /opt/jumphost/.env
```

### Port 22 Already in Use

If system SSH is on port 22:
```bash
# Change system SSH to different port
sudo sed -i 's/#Port 22/Port 2222/' /etc/ssh/sshd_config
sudo systemctl restart sshd

# Or change jumphost-ssh-proxy to different port in service file
```

---

## Post-Installation

1. **Change admin password** via web interface
2. **Add users** with source IPs
3. **Add backend servers** 
4. **Create server groups**
5. **Grant access policies**
6. **Test SSH connection**: `ssh -A user@jumphost-ip`
7. **Test RDP connection**: `mstsc /v:jumphost-ip:3389`
8. **Test MP4 conversion**: Create RDP session, click "Convert" in web UI

---

## Upgrading

```bash
cd /opt/jumphost
git fetch origin
git checkout v1.3  # or latest version
source venv/bin/activate
pip install --upgrade -r requirements.txt
alembic upgrade head
sudo systemctl restart jumphost-flask.service
sudo systemctl restart jumphost-ssh-proxy.service
sudo systemctl restart jumphost-rdp-proxy.service
sudo systemctl restart jumphost-mp4-converter@1.service
sudo systemctl restart jumphost-mp4-converter@2.service
```

**Important**: Re-apply PyRDP patches after upgrading pyrdp-mitm!

---

## Security Notes

- Change default admin password immediately
- Use strong database passwords
- Configure firewall (ports 22, 3389, 5000)
- Enable HTTPS for web interface (production)
- Regular backups of database and recordings
- Review audit logs regularly
- Consider IP whitelisting for admin interface

---

## Support

- Documentation: [DOCUMENTATION.md](DOCUMENTATION.md)
- Roadmap: [ROADMAP.md](ROADMAP.md)
- PyRDP Patches: [PYRDP_PATCHES.md](PYRDP_PATCHES.md)
- Issues: Check logs in `/var/log/jumphost/`

---

## Quick Reference

**Service Management**:
```bash
sudo systemctl {start|stop|restart|status} jumphost-flask.service
sudo systemctl {start|stop|restart|status} jumphost-ssh-proxy.service
sudo systemctl {start|stop|restart|status} jumphost-rdp-proxy.service
sudo systemctl {start|stop|restart|status} jumphost-mp4-converter@{1,2}.service
```

**Log Files**:
- Flask: `/var/log/jumphost/flask.log`
- SSH Proxy: `/var/log/jumphost/ssh_proxy.log`
- RDP Proxy: `/var/log/jumphost/rdp_mitm.log`
- MP4 Workers: `/var/log/jumphost/mp4-converter-worker{1,2}.log`

**Recordings**:
- SSH: `/var/log/jumphost/ssh_recordings/*.log`
- RDP: `/var/log/jumphost/rdp_recordings/replays/*.pyrdp`
- MP4: `/var/log/jumphost/rdp_recordings/mp4_cache/*.mp4`

**Database**:
- Migrations: `alembic upgrade head`
- Console: `psql -U jumphost -d jumphost`
- Backup: `pg_dump jumphost > backup.sql`

---

**Version**: 1.3  
**Last Updated**: January 2026

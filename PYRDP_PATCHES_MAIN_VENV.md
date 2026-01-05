# PyRDP Patches for Main Venv (RDP Proxy with Access Control)

This document describes patches applied to PyRDP in the **main venv** (`/opt/jumphost/venv`) for RDP proxy with access control integration.

**Note**: This is different from [PYRDP_PATCHES.md](PYRDP_PATCHES.md) which documents patches for `venv-pyrdp-converter` (MP4 conversion only).

## Overview

The main venv contains PyRDP MITM with deep integration into JumpHost's access control system:
- Dynamic backend routing based on destination IP
- Policy-based access control (V2 engine)
- Session tracking in database
- UTMP/WTMP logging
- Audit logging for all access attempts

## Patch Files

Patches are available in [`/opt/jumphost/patches/`](patches/) directory:

1. **pyrdp_core_mitm.patch** (17KB, 286 lines) - Main proxy logic with access control
2. **pyrdp_enum_rdp.patch** (909B, 28 lines) - RDP version support (Windows 11)
3. **pyrdp_mitm_filemapping.patch** (824B, 20 lines) - Python 3.13 compatibility

## Patch 1: Dynamic Backend Routing (core/mitm.py)

**File**: `venv/lib/python3.13/site-packages/pyrdp/core/mitm.py`

**Size**: 286 lines changed

**Purpose**: 
- Integrate JumpHost access control into PyRDP connection flow
- Route connections to correct backend based on policies
- Track sessions in database with UTMP logging

### Key Modifications

#### 1. Import JumpHost Modules

```python
# Add jumphost path for imports
sys.path.insert(0, '/opt/jumphost/src')
try:
    from core.database import SessionLocal, AuditLog, IPAllocation, Session as DBSession
    from core.access_control_v2 import AccessControlEngineV2
    from core.utmp_helper import write_utmp_login, write_utmp_logout
    from datetime import datetime
    import os
    JUMPHOST_ENABLED = True
except ImportError:
    JUMPHOST_ENABLED = False
    logging.warning("Jumphost modules not found, running in standard mode")
```

**Why**: Enables graceful fallback if running outside JumpHost environment.

#### 2. Initialize Access Control in Factory

```python
class MITMServerFactory(ServerFactory):
    def __init__(self, config: MITMConfig):
        self.config = config
        if JUMPHOST_ENABLED:
            self.access_control = AccessControlEngineV2()
            logging.getLogger(LOGGER_NAMES.MITM_CONNECTIONS).info("Jumphost access control V2 enabled")
```

**Why**: Creates single AccessControlEngineV2 instance shared across all connections.

#### 3. Wrap Protocol ConnectionMade

The main logic is injected by wrapping `protocol.connectionMade()`:

```python
def jumphost_connectionMade():
    # IMPORTANT: Always call original connectionMade first
    original_connectionMade()
    
    # Extract destination IP from socket
    sock = protocol.transport.socket
    dest_ip = sock.getsockname()[0]
    
    # Find backend by destination IP
    backend_lookup = protocol._jumphost_access_control.find_backend_by_proxy_ip(db, dest_ip)
    
    # Check access with V2 engine
    result = protocol._jumphost_access_control.check_access_v2(db, source_ip, dest_ip, 'rdp')
    
    if not result['has_access']:
        # Log denial and close connection
        audit = AuditLog(action='rdp_access_denied', ...)
        db.add(audit)
        db.commit()
        reactor.callLater(0, protocol.transport.loseConnection)
        return
    
    # Update MITM to target correct backend
    protocol._jumphost_mitm.state.effectiveTargetHost = grant_server.ip_address
    protocol._jumphost_mitm.state.effectiveTargetPort = 3389
    
    # Create/update session in database
    # ... (session tracking logic)
```

**Critical Points**:
- Must call `original_connectionMade()` FIRST to initialize PyRDP state
- Access control check happens BEFORE `connectToServer()` is triggered
- Backend routing is dynamic - each connection can go to different server

#### 4. Session Tracking

**Connection Multiplexing Detection**:
```python
# RDP clients often open multiple TCP connections for same session
# Only consider sessions started within last 10 seconds as part of same session
recent_threshold = datetime.utcnow() - timedelta(seconds=10)

existing_session = db.query(DBSession).filter(
    DBSession.source_ip == source_ip,
    DBSession.backend_ip == grant_server.ip_address,
    DBSession.protocol == 'rdp',
    DBSession.is_active == True,
    DBSession.started_at >= recent_threshold
).first()
```

**Why**: RDP connections have multiple TCP streams. We track the first one and ignore subsequent multiplexed connections within 10 seconds.

**Session Creation**:
```python
if not existing_session:
    # Find next available rdp slot (rdp0-rdp99)
    tty = find_next_utmp_slot('rdp')
    
    new_session = DBSession(
        session_id=sessionID,
        source_ip=source_ip,
        backend_ip=grant_server.ip_address,
        protocol='rdp',
        username=user.username,
        tty=tty,
        is_active=True,
        started_at=datetime.utcnow()
    )
    db.add(new_session)
    db.commit()
    
    # Write to UTMP for system-wide tracking
    write_utmp_login(tty, user.username, source_ip)
```

#### 5. Disconnect Handling

```python
original_connectionLost = protocol.connectionLost

def jumphost_connectionLost(reason):
    original_connectionLost(reason)
    
    # Update session in database
    session = db.query(DBSession).filter(
        DBSession.session_id == sessionID
    ).first()
    
    if session:
        session.is_active = False
        session.ended_at = datetime.utcnow()
        session.duration_seconds = (session.ended_at - session.started_at).total_seconds()
        
        # Update recording file size
        if os.path.exists(recording_path):
            session.recording_size = os.path.getsize(recording_path)
        
        db.commit()
        
        # Write UTMP logout
        write_utmp_logout(session.tty)
```

---

## Patch 2: RDP Version Support (enum/rdp.py)

**File**: `venv/lib/python3.13/site-packages/pyrdp/enum/rdp.py`

**Size**: 28 lines

**Same as venv-pyrdp-converter** - See [PYRDP_PATCHES.md](PYRDP_PATCHES.md#patch-1-rdp-version-support-enumrdppy)

Adds:
- `RDP10_12 = 0x80011` constant (Windows 11)
- `_missing_()` method for unknown versions

---

## Patch 3: Python 3.13 Compatibility (mitm/FileMapping.py)

**File**: `venv/lib/python3.13/site-packages/pyrdp/mitm/FileMapping.py`

**Size**: 20 lines

**Same as venv-pyrdp-converter** - See [PYRDP_PATCHES.md](PYRDP_PATCHES.md#patch-2-python-313-compatibility-mitmfilemappingpy)

Changes:
```python
# From:
from typing import io
# To:
from typing import BinaryIO
```

---

## Applying Patches

### Automated Application

```bash
cd /opt/jumphost
source venv/bin/activate

# Backup originals
cp venv/lib/python3.13/site-packages/pyrdp/core/mitm.py{,.orig}
cp venv/lib/python3.13/site-packages/pyrdp/enum/rdp.py{,.orig}
cp venv/lib/python3.13/site-packages/pyrdp/mitm/FileMapping.py{,.orig}

# Apply patches
patch -p0 < patches/pyrdp_core_mitm.patch
patch -p0 < patches/pyrdp_enum_rdp.patch
patch -p0 < patches/pyrdp_mitm_filemapping.patch
```

### Manual Application

If patches fail (due to line number changes):

1. **core/mitm.py**: Replace entire `buildProtocol()` method with patched version
2. **enum/rdp.py**: Add `RDP10_12` constant and `_missing_()` method
3. **mitm/FileMapping.py**: Change import statement

See patch files in [`patches/`](patches/) directory for exact changes.

---

## Verification

```bash
cd /opt/jumphost
source venv/bin/activate

# Test imports
python3 << EOF
import sys
sys.path.insert(0, '/opt/jumphost/src')
from pyrdp.core.mitm import MITMServerFactory
from pyrdp.enum.rdp import RDPVersion
print("Imports OK")
print(f"RDP10_12 exists: {hasattr(RDPVersion, 'RDP10_12')}")
EOF

# Test PyRDP works
pyrdp-mitm.py --version
```

Expected output:
```
Imports OK
RDP10_12 exists: True
PyRDP MITM 2.1.0
```

---

## Architecture Flow

```
Client connects to JumpHost:3389
    ↓
Twisted accepts connection (addr.host = source_ip)
    ↓
MITMServerFactory.buildProtocol(addr)
    ↓
Create RDPMITM instance
    ↓
Wrap protocol.connectionMade()
    ↓
[PyRDP Original] Initialize state, handlers, etc.
    ↓
[JumpHost Hook] Extract dest_ip from socket
    ↓
[JumpHost Hook] Find backend by dest_ip (IP allocation lookup)
    ↓
[JumpHost Hook] Check access (source_ip, dest_ip, 'rdp')
    ↓
If ACCESS DENIED:
    - Log to audit_logs
    - Close connection
    - Return
    ↓
If ACCESS GRANTED:
    - Update mitm.state.effectiveTargetHost = backend_ip
    - Create session in database
    - Write UTMP login (rdp0-rdp99)
    - Continue to PyRDP normal flow
    ↓
[PyRDP Original] Connect to backend server
    ↓
[PyRDP Original] Perform MITM, record session
    ↓
On disconnect:
    ↓
[JumpHost Hook] Update session (ended_at, duration, file_size)
    ↓
[JumpHost Hook] Write UTMP logout
```

---

## Key Design Decisions

### 1. Why Wrap connectionMade()?

**Problem**: PyRDP's `buildProtocol()` creates MITM with fixed config (target host/port).

**Solution**: Wrap `connectionMade()` to inject logic AFTER PyRDP initializes but BEFORE it connects to backend.

**Alternatives Considered**:
- ❌ Modify config before creating MITM - Too late, can't get dest_ip yet
- ❌ Create custom Protocol subclass - Would break PyRDP's internal protocol chain
- ✅ Wrap connectionMade() - Clean hook point, non-invasive

### 2. Why 10-Second Window for Multiplexing?

**Problem**: RDP opens multiple TCP connections (channels). Need to track as single session.

**Observation**: All multiplexed connections arrive within ~2 seconds of first connection.

**Safety Margin**: 10 seconds ensures we catch delayed connections while not merging unrelated sessions.

**Alternative**: Could use RDP session ID from protocol, but it's not available at connection time.

### 3. Why Store Backend in Session Table?

**Problem**: Need to know which backend to reconnect to for failover/monitoring.

**Solution**: Store `backend_ip` in sessions table, not just user/source_ip.

**Benefit**: Can rebuild full connection graph from database for troubleshooting.

---

## Troubleshooting

### Patch Doesn't Apply

```bash
# Check if already patched
grep "JUMPHOST_ENABLED" venv/lib/python3.13/site-packages/pyrdp/core/mitm.py

# If yes, restore original and reapply
cp venv/lib/python3.13/site-packages/pyrdp/core/mitm.py{.orig,}
patch -p0 < patches/pyrdp_core_mitm.patch
```

### Import Errors

```bash
# Check sys.path includes jumphost
python3 << EOF
import sys
print('/opt/jumphost/src' in sys.path)
sys.path.insert(0, '/opt/jumphost/src')
from core.database import SessionLocal
print("Import OK")
EOF
```

### Access Denied for All Connections

```bash
# Check database has policies
cd /opt/jumphost
source venv/bin/activate
python3 << EOF
from src.core.database import SessionLocal, AccessPolicy
db = SessionLocal()
print(f"Policies: {db.query(AccessPolicy).count()}")
EOF
```

### Backend Not Found

```bash
# Check IP allocation table
python3 << EOF
from src.core.database import SessionLocal, IPAllocation
db = SessionLocal()
allocs = db.query(IPAllocation).all()
for a in allocs:
    print(f"{a.proxy_ip} -> {a.server.ip_address}")
EOF
```

---

## Maintenance Notes

### After Upgrading PyRDP

```bash
pip install --upgrade pyrdp-mitm
# RE-APPLY ALL PATCHES!
cd /opt/jumphost
patch -p0 < patches/pyrdp_core_mitm.patch
patch -p0 < patches/pyrdp_enum_rdp.patch
patch -p0 < patches/pyrdp_mitm_filemapping.patch
```

### Creating New Patch

After modifying PyRDP files:

```bash
# Create clean venv with original PyRDP
python3 -m venv /tmp/venv-pyrdp-clean
source /tmp/venv-pyrdp-clean/bin/activate
pip install pyrdp-mitm==2.1.0

# Generate diff
diff -u /tmp/venv-pyrdp-clean/lib/python3.13/site-packages/pyrdp/core/mitm.py \
        /opt/jumphost/venv/lib/python3.13/site-packages/pyrdp/core/mitm.py \
        > patches/pyrdp_core_mitm.patch
```

---

## Security Considerations

### 1. Hardcoded Path

```python
sys.path.insert(0, '/opt/jumphost/src')
```

**Risk**: Assumes fixed installation path.

**Mitigation**: Could use environment variable `JUMPHOST_PATH`.

### 2. Database Credentials

Credentials loaded from `/opt/jumphost/.env` (hardcoded in database.py).

**Risk**: If .env is compromised, database access is compromised.

**Mitigation**: Ensure .env has proper permissions (600).

### 3. UTMP/WTMP Logging

Requires root to write to `/var/run/utmp`.

**Current**: RDP proxy runs as root.

**Future**: Consider using setuid helper or D-Bus service.

---

## Future Improvements

### 1. Configurable Multiplexing Window

Currently hardcoded to 10 seconds:

```python
recent_threshold = datetime.utcnow() - timedelta(seconds=10)
```

Could be configuration option.

### 2. Protocol-Level Session ID

Use RDP session ID from protocol handshake instead of time-based window.

**Challenge**: Not available at `connectionMade()` time.

### 3. Connection Pooling

Reuse database connections instead of creating new SessionLocal() per connection.

**Benefit**: Reduce overhead for high-traffic scenarios.

### 4. Upstream Contribution

Submit patches to PyRDP project:
- Hook system for custom access control
- Plugin architecture for extensions

---

## Related Documentation

- [PYRDP_PATCHES.md](PYRDP_PATCHES.md) - MP4 converter patches (venv-pyrdp-converter)
- [INSTALL.md](INSTALL.md) - Installation guide
- [DOCUMENTATION.md](DOCUMENTATION.md) - Architecture overview
- [FLEXIBLE_ACCESS_CONTROL_V2.md](FLEXIBLE_ACCESS_CONTROL_V2.md) - Policy system

---

**Version**: 1.3  
**Last Updated**: January 2026  
**PyRDP Version**: 2.1.0  
**Python**: 3.13

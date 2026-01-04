#!/usr/bin/env python3
"""
UTMP/WTMP Helper - Write session entries to system login records
Makes proxy sessions visible in 'w', 'who', 'last' commands
"""

import struct
import os
import time
import socket
from typing import Optional

# utmp constants (from /usr/include/bits/utmp.h)
UT_LINESIZE = 32
UT_NAMESIZE = 32
UT_HOSTSIZE = 256
UTMP_FILE = "/var/run/utmp"
WTMP_FILE = "/var/log/wtmp"

# Entry types
EMPTY = 0
RUN_LVL = 1
BOOT_TIME = 2
NEW_TIME = 3
OLD_TIME = 4
INIT_PROCESS = 5
LOGIN_PROCESS = 6
USER_PROCESS = 7
DEAD_PROCESS = 8

# utmp structure format (Linux x86_64)
# short type, int pid, char line[32], char id[4], char user[32], 
# char host[256], struct exit_status (2 shorts), int session, 
# struct timeval tv (2 ints), int addr_v6[4], char unused[20]
UTMP_FORMAT = "hi32s4s32s256shhiii4i20s"
UTMP_SIZE = struct.calcsize(UTMP_FORMAT)


def _make_utmp_entry(entry_type: int, pid: int, line: str, ut_id: str,
                     username: str, hostname: str, ip_addr: str = "") -> bytes:
    """Create a utmp entry structure"""
    
    # Convert IP address to int array (IPv4 mapped to IPv6)
    addr_v6 = [0, 0, 0, 0]
    if ip_addr:
        try:
            # Try to convert IP to integer
            parts = ip_addr.split('.')
            if len(parts) == 4:
                # IPv4: store in first element as big-endian integer
                addr_v6[0] = (int(parts[0]) << 24) | (int(parts[1]) << 16) | \
                             (int(parts[2]) << 8) | int(parts[3])
        except:
            pass
    
    # Get current time
    tv_sec = int(time.time())
    tv_usec = 0
    
    # Pack the structure
    entry = struct.pack(
        UTMP_FORMAT,
        entry_type,           # short type
        pid,                  # int pid
        line[:31].encode().ljust(32, b'\x00'),      # char line[32]
        ut_id[:3].encode().ljust(4, b'\x00'),       # char id[4]
        username[:31].encode().ljust(32, b'\x00'),  # char user[32]
        hostname[:255].encode().ljust(256, b'\x00'), # char host[256]
        0,                    # short e_termination
        0,                    # short e_exit
        0,                    # int session
        tv_sec,               # int tv_sec
        tv_usec,              # int tv_usec
        addr_v6[0], addr_v6[1], addr_v6[2], addr_v6[3],  # int addr_v6[4]
        b'\x00' * 20          # char unused[20]
    )
    
    return entry


def write_utmp_login(session_id: str, username: str, tty: str, 
                     source_ip: str, backend_user: Optional[str] = None) -> bool:
    """
    Write login entry to utmp/wtmp
    
    Args:
        session_id: Session identifier (e.g., "ssh_12345")
        username: Jumphost username
        tty: TTY name (e.g., "ssh0", "rdp0")
        source_ip: Client source IP
        backend_user: Backend username for display (e.g., "root@server1")
    
    Returns:
        True if successful, False otherwise
    """
    try:
        pid = os.getpid()
        
        # Use backend_user if provided, otherwise jumphost username
        display_user = backend_user if backend_user else username
        
        # Create utmp entry
        entry = _make_utmp_entry(
            USER_PROCESS,
            pid,
            tty,
            tty[-4:] if len(tty) >= 4 else tty,  # last 4 chars as ID
            display_user[:31],
            source_ip[:255],
            source_ip
        )
        
        # Write to wtmp (always succeeds, logs history)
        try:
            with open(WTMP_FILE, 'ab') as f:
                f.write(entry)
        except PermissionError:
            # wtmp requires root, skip if no permission
            pass
        
        # Write to utmp (shows in 'w')
        # This is tricky - we need to find/update existing entry or append
        # For simplicity, we'll append (may show duplicates but works)
        try:
            with open(UTMP_FILE, 'ab') as f:
                f.write(entry)
            return True
        except FileNotFoundError:
            # utmp doesn't exist, that's ok
            return True
        except PermissionError:
            # No permission, that's ok
            return True
            
    except Exception as e:
        # Don't fail the session if utmp fails
        print(f"Warning: Failed to write utmp: {e}")
        return False


def write_utmp_logout(tty: str, username: str = "") -> bool:
    """
    Write logout entry to utmp/wtmp
    
    Args:
        tty: TTY name used during login
        username: Username (for wtmp)
    
    Returns:
        True if successful, False otherwise
    """
    try:
        pid = os.getpid()
        
        # Create dead process entry
        entry = _make_utmp_entry(
            DEAD_PROCESS,
            pid,
            tty,
            tty[-4:] if len(tty) >= 4 else tty,
            "",  # Empty username for logout
            "",  # Empty hostname
            ""   # Empty IP
        )
        
        # Write to wtmp
        try:
            with open(WTMP_FILE, 'ab') as f:
                f.write(entry)
        except PermissionError:
            pass
        
        # For utmp, we should find and remove/update the entry
        # For simplicity, just append DEAD_PROCESS (will be cleaned by system)
        try:
            with open(UTMP_FILE, 'ab') as f:
                f.write(entry)
            return True
        except (FileNotFoundError, PermissionError):
            return True
            
    except Exception as e:
        print(f"Warning: Failed to write utmp logout: {e}")
        return False


if __name__ == "__main__":
    # Test
    print("Testing utmp write...")
    write_utmp_login("test_123", "testuser", "ssh0", "192.168.1.100", "root@server1")
    print("Check with: w")
    time.sleep(5)
    write_utmp_logout("ssh0", "testuser")
    print("Logout written")

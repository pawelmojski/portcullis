#!/usr/bin/env python3
"""
SSH Proxy Server with session recording
Intercepts SSH connections, validates access, forwards to backend, and records sessions
"""
import os
import sys
import json
import socket
import select
import threading
import logging
import time
from datetime import datetime
from pathlib import Path
import paramiko
import pytz

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.core.database import SessionLocal, User, Server, AccessGrant, Session as DBSession
from src.core.access_control_v2 import AccessControlEngineV2 as AccessControl
from src.core.ip_pool import IPPoolManager
from src.core.utmp_helper import write_utmp_login, write_utmp_logout
from src.core.database import SessionTransfer

# Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/var/log/jumphost/ssh_proxy.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('ssh_proxy')


class SSHSessionRecorder:
    """Records SSH session I/O to file with live writing"""
    
    def __init__(self, session_id: str, username: str, server_ip: str):
        self.session_id = session_id
        self.username = username
        self.server_ip = server_ip
        self.start_time = datetime.now()
        
        # Create recording file
        timestamp = self.start_time.strftime("%Y%m%d_%H%M%S")
        filename = f"{timestamp}_{username}_{server_ip.replace('.', '_')}_{session_id}.log"
        self.log_file = Path(f"/var/log/jumphost/ssh_recordings/{filename}")
        self.recording_file = str(self.log_file)  # For compatibility
        
        # Initialize file with metadata header
        self.metadata = {
            'session_id': session_id,
            'username': username,
            'server_ip': server_ip,
            'start_time': self.start_time.isoformat(),
            'events': []
        }
        
        # Create file immediately and write initial structure
        with open(self.log_file, 'w') as f:
            json.dump(self.metadata, f, indent=2)
        
        self.event_count = 0
        logger.info(f"Recording session to: {self.log_file}")
    
    def record_event(self, event_type: str, data: str):
        """Record an event and write immediately to file"""
        event = {
            'timestamp': datetime.now().isoformat(),
            'type': event_type,
            'data': data if len(data) < 1000 else data[:1000] + '... [truncated]'
        }
        
        # Read current file, add event, write back
        try:
            with open(self.log_file, 'r') as f:
                file_data = json.load(f)
            
            file_data['events'].append(event)
            
            with open(self.log_file, 'w') as f:
                json.dump(file_data, f, indent=2)
                f.flush()  # Force write to disk
            
            self.event_count += 1
        except Exception as e:
            logger.error(f"Failed to write event to recording: {e}")
    
    def save(self):
        """Finalize recording with end metadata"""
        try:
            with open(self.log_file, 'r') as f:
                file_data = json.load(f)
            
            file_data['end_time'] = datetime.now().isoformat()
            file_data['duration_seconds'] = (datetime.now() - self.start_time).total_seconds()
            
            with open(self.log_file, 'w') as f:
                json.dump(file_data, f, indent=2)
            
            logger.info(f"Session recording saved: {self.log_file} ({self.event_count} events)")
        except Exception as e:
            logger.error(f"Failed to finalize recording: {e}")


class SSHProxyHandler(paramiko.ServerInterface):
    """Handles SSH authentication and channel requests"""
    
    def __init__(self, source_ip: str, dest_ip: str, db_session):
        self.source_ip = source_ip
        self.dest_ip = dest_ip  # NEW: destination IP client connected to
        self.db = db_session
        self.access_control = AccessControl()
        self.authenticated_user = None
        self.target_server = None
        self.matching_policies = []  # Policies that granted access
        self.client_password = None
        self.client_key = None
        self.agent_channel = None  # For agent forwarding
        self.no_grant_reason = None  # Reason for no grant (for banner message)
        
        # EARLY grant check - BEFORE get_banner() is called
        # We check if source IP has ANY policy for this dest (any username)
        # This allows us to show banner early if IP has no access at all
        logger.info(f"SSHProxyHandler init: early check for {source_ip} -> {dest_ip}")
        try:
            backend_lookup = self.access_control.find_backend_by_proxy_ip(self.db, self.dest_ip)
            if not backend_lookup:
                logger.warning(f"No backend found for {self.dest_ip}")
                self.no_grant_reason = "No backend server configuration found"
            else:
                # Quick check: does this source IP have ANY active grant to this backend?
                # We use empty username - check_access_v2 will look for any matching policy
                result = self.access_control.check_access_v2(
                    self.db,
                    self.source_ip,
                    self.dest_ip,
                    'ssh',
                    ''  # Empty username = check for any grant from this IP
                )
                
                if not result['has_access']:
                    logger.warning(f"No grant for IP {self.source_ip} to {self.dest_ip}: {result['reason']}")
                    self.no_grant_reason = result.get('reason', 'No active grant found for your IP address')
                else:
                    logger.info(f"Grant found for {self.source_ip}, proceeding with auth")
                    
        except Exception as e:
            logger.error(f"Error in early grant check: {e}", exc_info=True)
        
        # PTY parameters from client
        self.pty_term = None
        self.pty_width = None
        self.pty_height = None
        self.pty_modes = None
        # Channel type and exec command
        self.channel_type = None  # 'shell', 'exec', or 'subsystem'
        self.exec_command = None
        self.subsystem_name = None
        self.ssh_login = None  # SSH login name for backend
        # Port forwarding destinations
        self.forward_destinations = {}  # chanid -> (host, port)
        
    def check_auth_none(self, username: str):
        """Check 'none' authentication - called first before any real auth
        
        This is the perfect place to reject users without grants EARLY,
        before they are prompted for password.
        
        Return AUTH_FAILED to proceed with other auth methods.
        Return AUTH_SUCCESSFUL only if auth should succeed without password.
        """
        logger.info(f"check_auth_none called for {username} from {self.source_ip}")
        
        # Pre-check: does this user have ANY active policy?
        try:
            backend_lookup = self.access_control.find_backend_by_proxy_ip(self.db, self.dest_ip)
            if not backend_lookup:
                logger.warning(f"No backend found for {self.dest_ip}, denying {username} from {self.source_ip}")
                self.no_grant_reason = "No backend server configuration found"
                logger.info(f"check_auth_none: SET no_grant_reason='{self.no_grant_reason}'")
                # Return FAILED but banner will be shown
                return paramiko.AUTH_FAILED
            
            logger.info(f"check_auth_none: backend found, checking access...")
            # Quick access check
            result = self.access_control.check_access_v2(
                self.db,
                self.source_ip,
                self.dest_ip,
                'ssh',
                username
            )
            
            logger.info(f"check_auth_none: access check result: has_access={result['has_access']}, reason={result.get('reason')}")
            
            if not result['has_access']:
                logger.warning(f"No grant for {username} from {self.source_ip}: {result['reason']}")
                self.no_grant_reason = result.get('reason', 'No active grant found')
                logger.info(f"check_auth_none: SET no_grant_reason='{self.no_grant_reason}'")
                # Return FAILED - user will be disconnected after banner
                return paramiko.AUTH_FAILED
            
            logger.info(f"check_auth_none: access granted, proceeding with normal auth")
                
        except Exception as e:
            logger.error(f"Error checking grants in check_auth_none: {e}", exc_info=True)
        
        # Grant exists - proceed with normal auth flow
        return paramiko.AUTH_FAILED  # Still need password/key
        
    def check_auth_password(self, username: str, password: str):
        """Check password authentication"""
        logger.info(f"Auth attempt: {username} from {self.source_ip} to {self.dest_ip}")
        
        # First, find backend server by destination IP
        backend_lookup = self.access_control.find_backend_by_proxy_ip(self.db, self.dest_ip)
        if not backend_lookup:
            logger.error(f"No backend server found for destination IP {self.dest_ip}")
            return paramiko.AUTH_FAILED
        
        backend_server = backend_lookup['server']
        
        # Check access permissions using V2 engine
        result = self.access_control.check_access_v2(
            self.db, 
            self.source_ip, 
            self.dest_ip, 
            'ssh',
            username  # SSH login
        )
        
        if not result['has_access']:
            logger.warning(f"Access denied for {username} from {self.source_ip}: {result['reason']}")
            # Store reason for banner
            self.no_grant_reason = result.get('reason', 'No active grant found for your IP address')
            return paramiko.AUTH_FAILED
        
        # All checks passed
        self.target_server = result['server']
        self.authenticated_user = result['user']
        self.matching_policies = result.get('policies', [])
        self.access_result = result  # Store full result for effective_end_time
        self.ssh_login = username  # SSH login for backend (e.g., "ideo")
        self.client_password = password
        
        logger.info(f"Access granted: {username} → {self.target_server.ip_address} (via {self.dest_ip})")
        return paramiko.AUTH_SUCCESSFUL
    
    def check_auth_publickey(self, username: str, key):
        """Check public key authentication by testing it on backend server.
        
        This is the correct approach:
        1. Check if user has access policy
        2. Try to authenticate to backend with this key
        3. If backend accepts key → AUTH_SUCCESSFUL
        4. If backend rejects key → AUTH_FAILED (client will try password)
        """
        logger.info(f"Pubkey auth attempt: {username} from {self.source_ip} to {self.dest_ip}, key type: {key.get_name()}")
        
        # First, find backend server by destination IP
        backend_lookup = self.access_control.find_backend_by_proxy_ip(self.db, self.dest_ip)
        if not backend_lookup:
            logger.error(f"No backend server found for destination IP {self.dest_ip}")
            return paramiko.AUTH_FAILED
        
        backend_server = backend_lookup['server']
        
        # Check access permissions using V2 engine
        result = self.access_control.check_access_v2(
            self.db,
            self.source_ip,
            self.dest_ip,
            'ssh',
            username  # SSH login
        )
        
        if not result['has_access']:
            logger.warning(f"Access denied for {username} from {self.source_ip}: {result['reason']}")
            # Store reason for banner
            self.no_grant_reason = result.get('reason', 'No active grant found for your IP address')
            return paramiko.AUTH_FAILED
        
        # Accept pubkey - backend will verify agent forwarding works
        # If agent fails, we'll disconnect properly for password retry
        logger.info(f"Pubkey accepted - will verify agent forwarding in backend")
        
        # Store authentication info
        self.target_server = result['server']
        self.authenticated_user = result['user']
        self.matching_policies = result.get('policies', [])
        self.access_result = result  # Store full result for effective_end_time
        self.ssh_login = username  # SSH login for backend (e.g., "ideo")
        self.client_key = key
        
        return paramiko.AUTH_SUCCESSFUL
    
    def get_allowed_auths(self, username):
        """Return allowed authentication methods
        
        This is called AFTER check_auth_none. If check_auth_none already
        determined there's no grant, we return ONLY "publickey" (which will fail)
        to prevent password prompt from appearing.
        """
        if self.no_grant_reason:
            logger.info(f"get_allowed_auths: no grant detected, returning 'publickey' only (will fail)")
            return "publickey"
        
        logger.info(f"get_allowed_auths: grant OK, allowing publickey,password")
        return "publickey,password"
    
    def get_banner(self):
        """Return SSH banner message
        
        If user has no grant, return a polite rejection message.
        Must return tuple (banner, language) - default is (None, None).
        """
        logger.info(f"get_banner called, no_grant_reason={self.no_grant_reason}")
        if self.no_grant_reason:
            banner = (
                f"\r\n"
                f"+====================================================================+\r\n"
                f"|                          ACCESS DENIED                             |\r\n"
                f"+====================================================================+\r\n"
                f"\r\n"
                f"  Dear user,\r\n"
                f"\r\n"
                f"  There is no active access grant for your IP address:\r\n"
                f"    {self.source_ip}\r\n"
                f"\r\n"
                f"  Reason: {self.no_grant_reason}\r\n"
                f"\r\n"
                f"  Please contact your administrator to request access.\r\n"
                f"\r\n"
                f"  Have a nice day!\r\n"
                f"\r\n"
            )
            logger.info(f"get_banner returning banner message ({len(banner)} chars)")
            return (banner, "en-US")
        
        # No banner - return default as per paramiko docs
        return (None, None)
    
    def check_channel_request(self, kind: str, chanid: int):
        """Allow session, direct-tcpip (port forwarding -L) and dynamic-tcpip (SOCKS -D) channel requests"""
        logger.info(f"Channel request: kind={kind}, chanid={chanid}")
        if kind == 'session':
            return paramiko.OPEN_SUCCEEDED
        elif kind == 'direct-tcpip':
            # Port forwarding (-L local forward)
            return paramiko.OPEN_SUCCEEDED
        elif kind == 'dynamic-tcpip':
            # SOCKS proxy (-D dynamic forward)
            return paramiko.OPEN_SUCCEEDED
        return paramiko.OPEN_FAILED_ADMINISTRATIVELY_PROHIBITED
    
    def check_channel_pty_request(self, channel, term, width, height, pixelwidth, pixelheight, modes):
        """Allow PTY requests and save parameters"""
        logger.info(f"PTY request: term={term}, width={width}, height={height}")
        # Save PTY parameters to use for backend connection
        self.pty_term = term
        self.pty_width = width
        self.pty_height = height
        self.pty_modes = modes
        return True
    
    def check_channel_shell_request(self, channel):
        """Allow shell requests"""
        logger.info("Shell request received")
        self.channel_type = 'shell'
        return True
    
    def check_channel_exec_request(self, channel, command):
        """Allow exec requests (for SCP, etc)"""
        cmd_str = command.decode('utf-8') if isinstance(command, bytes) else command
        logger.info(f"Exec request: {cmd_str}")
        self.channel_type = 'exec'
        self.exec_command = command
        return True
    
    def check_channel_subsystem_request(self, channel, name):
        """Allow subsystem requests (for SFTP/SCP)"""
        subsys_name = name.decode('utf-8') if isinstance(name, bytes) else name
        logger.info(f"Subsystem request: {subsys_name}")
        self.channel_type = 'subsystem'
        self.subsystem_name = name
        return True
    
    def check_channel_forward_agent_request(self, channel):
        """Allow agent forwarding and setup handler"""
        logger.info("Client requested agent forwarding")
        # Store the channel for later use
        self.agent_channel = channel
        return True
    
    def check_port_forward_request(self, address, port):
        """Handle tcpip-forward requests for remote port forwarding (-R)
        
        For -R, we open the port locally on the jump host and forward 
        connections to the client via SSH channel.
        
        Args:
            address: Address to bind (usually '' or 'localhost')
            port: Port to bind
            
        Note: SSH protocol does NOT send the destination (e.g. localhost:8080 from -R 9090:localhost:8080).
        We only know the bind address/port. The destination is stored only on client side.
        """
        logger.info(f"Remote forward request: bind {address}:{port} (destination unknown - SSH protocol limitation)")
        
        # Check if user has port forwarding permission
        access_control = AccessControl()
        
        allowed = access_control.check_port_forwarding_allowed(
            self.db,
            self.source_ip,
            self.dest_ip
        )
        
        if not allowed:
            logger.warning(f"Remote port forwarding denied for source {self.source_ip}")
            return False
        
        logger.info(f"Remote port forwarding allowed for {address}:{port}")
        
        # Store the request so we can open the port later
        # (after we have the transport object)
        # ASSUMPTION: We assume -R forwards to the same port (e.g. -R 9090:localhost:9090)
        # because SSH protocol doesn't send destination in tcpip-forward message
        if not hasattr(self, 'remote_forward_requests'):
            self.remote_forward_requests = []
        self.remote_forward_requests.append((address, port))
        
        return port  # Return the port that will be bound
    
    def cancel_port_forward_request(self, address, port):
        """Handle cancel-tcpip-forward requests"""
        logger.info(f"Cancel remote forward: {address}:{port}")
        return True
    
    def check_channel_direct_tcpip_request(self, chanid, origin, destination):
        """Handle direct-tcpip requests for port forwarding (-L)
        
        Args:
            chanid: Channel ID
            origin: (host, port) where client is connecting from
            destination: (host, port) where client wants to connect to
        """
        logger.info(f"Direct-TCPIP request: {origin} -> {destination}")
        
        # Check if user has port forwarding permission
        access_control = AccessControl()
        
        allowed = access_control.check_port_forwarding_allowed(
            self.db,
            self.source_ip,
            self.dest_ip
        )
        
        if not allowed:
            logger.warning(f"Port forwarding denied for source {self.source_ip}")
            return paramiko.OPEN_FAILED_ADMINISTRATIVELY_PROHIBITED
        
        # Store destination for the forwarding handler
        self.forward_destinations = getattr(self, 'forward_destinations', {})
        self.forward_destinations[chanid] = destination
        
        logger.info(f"Port forwarding allowed to {destination}")
        return paramiko.OPEN_SUCCEEDED


class SSHProxyServer:
    """SSH Proxy Server - intercepts and forwards connections"""
    
    def __init__(self, host='10.0.160.129', port=22):
        self.host = host
        self.port = port
        self.host_key = self._load_or_generate_host_key()
        
    def _load_or_generate_host_key(self):
        """Load or generate SSH host key"""
        key_file = Path('/opt/jumphost/ssh_host_key')
        
        if key_file.exists():
            return paramiko.RSAKey(filename=str(key_file))
        else:
            logger.info("Generating new SSH host key...")
            key = paramiko.RSAKey.generate(2048)
            key.write_private_key_file(str(key_file))
            return key
    
    def forward_channel(self, client_channel, backend_channel, recorder: SSHSessionRecorder = None, db_session_id=None, is_sftp=False):
        """Forward data between client and backend server via SSH channels"""
        bytes_sent = 0
        bytes_received = 0
        sftp_transfer_id = None
        
        # For SFTP, create transfer record
        if is_sftp and db_session_id:
            try:
                sftp_transfer_id = self.log_sftp_transfer(db_session_id)
            except Exception as e:
                logger.error(f"Failed to create SFTP transfer record: {e}")
        
        try:
            while True:
                # Check if channels are still open
                if client_channel.closed or backend_channel.closed:
                    break
                
                r, w, x = select.select([client_channel, backend_channel], [], [], 1.0)
                
                if client_channel in r:
                    data = client_channel.recv(4096)
                    if len(data) == 0:
                        break
                    backend_channel.send(data)
                    bytes_sent += len(data)
                    if recorder:
                        recorder.record_event('client_to_server', data.decode('utf-8', errors='ignore'))
                
                if backend_channel in r:
                    data = backend_channel.recv(4096)
                    if len(data) == 0:
                        break
                    client_channel.send(data)
                    bytes_received += len(data)
                    if recorder:
                        recorder.record_event('server_to_client', data.decode('utf-8', errors='ignore'))
        
        except Exception as e:
            logger.debug(f"Channel forwarding ended: {e}")
        
        finally:
            # Update SFTP transfer stats
            if is_sftp and sftp_transfer_id:
                try:
                    self.update_transfer_stats(sftp_transfer_id, bytes_sent, bytes_received)
                    logger.info(f"SFTP transfer completed: sent={bytes_sent} bytes, received={bytes_received} bytes")
                except Exception as e:
                    logger.error(f"Failed to update SFTP transfer stats: {e}")
            
            # Give client time to send DISCONNECT message
            import time
            time.sleep(0.1)
            
            # Close channels gracefully if still open
            try:
                if not client_channel.closed:
                    client_channel.close()
            except:
                pass
            try:
                if not backend_channel.closed:
                    backend_channel.close()
            except:
                pass
    
    def handle_port_forwarding(self, client_transport, backend_transport, server_handler, user, target_server):
        """Handle port forwarding requests (-L, -R, -D)
        
        Monitors client transport for new channel requests and forwards them to backend.
        This runs in a background thread while the main session is active.
        """
        try:
            logger.info(f"Port forwarding handler started for {user.username}")
            
            # Wait for transport to become fully active
            while not client_transport.is_active():
                import time
                time.sleep(0.1)
            
            # Continuously accept new forwarding channels
            while client_transport.is_active():
                try:
                    # Accept new channel with short timeout
                    channel = client_transport.accept(timeout=1.0)
                    
                    if channel is None:
                        continue
                    
                    # Get the destination for this channel
                    chanid = channel.get_id()
                    destination = server_handler.forward_destinations.get(chanid)
                    
                    if not destination:
                        logger.warning(f"No destination found for channel {chanid}")
                        channel.close()
                        continue
                    
                    dest_addr, dest_port = destination
                    logger.info(f"Forwarding channel {chanid} to {dest_addr}:{dest_port}")
                    
                    # Log port forward to database
                    transfer_id = None
                    db_session = getattr(server_handler, 'db_session', None)
                    if db_session:
                        try:
                            # Get local address/port from channel
                            local_addr, local_port = channel.getpeername() if hasattr(channel, 'getpeername') else ('unknown', 0)
                            transfer_id = self.log_port_forward(
                                db_session.id,
                                'port_forward_local',  # -L
                                local_addr,
                                local_port,
                                dest_addr,
                                dest_port
                            )
                        except Exception as e:
                            logger.error(f"Failed to log port forward: {e}")
                    
                    # Open corresponding channel on backend
                    try:
                        # For direct-tcpip, we need to connect from backend to the target
                        backend_channel = backend_transport.open_channel(
                            'direct-tcpip',
                            (dest_addr, dest_port),
                            ('127.0.0.1', 0)  # Our address from backend's perspective
                        )
                        
                        # Start forwarding in a new thread
                        forward_thread = threading.Thread(
                            target=self.forward_port_channel,
                            args=(channel, backend_channel, dest_addr, dest_port, transfer_id),
                            daemon=True
                        )
                        forward_thread.start()
                        logger.info(f"Started forwarding thread for {dest_addr}:{dest_port}")
                        
                    except Exception as e:
                        logger.error(f"Failed to open backend channel: {e}")
                        channel.close()
                        
                except Exception as e:
                    if "timeout" not in str(e).lower():
                        logger.debug(f"Accept error: {e}")
            
            logger.info("Port forwarding handler exiting (transport inactive)")
            
        except Exception as e:
            logger.error(f"Port forwarding handler error: {e}", exc_info=True)
    
    def handle_reverse_forwarding(self, client_transport, backend_transport, server_handler, port_map):
        """Handle reverse port forwarding (-R) from backend to client
        
        Args:
            port_map: Dict mapping backend port -> (client_addr, client_port)
        
        When someone connects to a port on backend that was opened by -R,
        backend sends us a channel that we need to forward to client.
        """
        try:
            logger.info("Reverse forwarding handler started")
            
            # Wait for backend transport to become active
            while not backend_transport.is_active():
                import time
                time.sleep(0.1)
            
            # Accept channels from backend
            while backend_transport.is_active() and client_transport.is_active():
                try:
                    # Accept channel from backend with timeout
                    backend_channel = backend_transport.accept(timeout=1.0)
                    
                    if backend_channel is None:
                        continue
                    
                    logger.info(f"Got reverse forward channel from backend")
                    
                    # Get channel info - for forwarded-tcpip, paramiko should have this
                    # We need to extract where backend wants us to connect
                    origin = getattr(backend_channel, 'origin_addr', ('unknown', 0))
                    
                    logger.info(f"Reverse forward from backend: {origin}")
                    
                    # Open channel to client - this should trigger client to connect locally
                    # For -R, client expects forwarded-tcpip channel
                    try:
                        # We need to forward this back to client
                        # The client will handle connecting to its local service
                        
                        # Just forward the existing backend channel to client
                        # Client transport should accept this as forwarded-tcpip
                        
                        # Start forwarding thread
                        forward_thread = threading.Thread(
                            target=self.forward_reverse_channel,
                            args=(client_transport, backend_channel, origin, port_map),
                            daemon=True
                        )
                        forward_thread.start()
                        
                    except Exception as e:
                        logger.error(f"Failed to setup reverse forward: {e}")
                        backend_channel.close()
                        
                except Exception as e:
                    if "timeout" not in str(e).lower():
                        logger.debug(f"Reverse accept error: {e}")
            
            logger.info("Reverse forwarding handler exiting")
            
        except Exception as e:
            logger.error(f"Reverse forwarding handler error: {e}", exc_info=True)
    
    def forward_reverse_channel(self, client_transport, backend_channel, origin, port_map):
        """Forward a reverse channel from backend to client
        
        Args:
            port_map: Dict mapping backend port -> (client_addr, client_port)
        
        When someone connects to the forwarded port on backend, backend opens
        a channel to us. We need to relay this to the client, which will
        connect to its local service.
        """
        try:
            # For now, if we only have one mapping, use it
            if len(port_map) == 1:
                dest_addr, dest_port = list(port_map.values())[0]
                logger.info(f"Using single port mapping: {dest_addr}:{dest_port}")
            else:
                logger.error(f"Multiple port mappings not yet supported: {port_map}")
                backend_channel.close()
                return
            
            # Instead of trying to open SSH channel to client (which fails),
            # we need to make client open a channel to US and connect to localhost:8080
            # The way to do this is to send a forwarded-tcpip channel request
            
            # Try using the proper paramiko method for server-initiated forwarded-tcpip
            try:
                # Get the Transport object's  channel open method
                # We need to manually craft the channel open request
                from paramiko import Channel
                from paramiko.common import cMSG_CHANNEL_OPEN
                
                # Create a new channel on client transport
                chanid = client_transport._next_channel()
                chan = Channel(chanid)
                client_transport._channels.put(chanid, chan)
                
                m = paramiko.Message()
                m.add_byte(cMSG_CHANNEL_OPEN)
                m.add_string('forwarded-tcpip')
                m.add_int(chanid)
                m.add_int(chan.in_window_size)
                m.add_int(chan.in_max_packet_size)
                m.add_string(dest_addr)  # Address to connect to on client
                m.add_int(dest_port)  # Port to connect to on client
                m.add_string(origin[0])  # Origin address
                m.add_int(origin[1])  # Origin port
                
                client_transport._send_user_message(m)
                chan._wait_for_event()
                
                logger.info(f"Opened forwarded-tcpip channel to client {dest_addr}:{dest_port}")
                
                # Forward data
                self.forward_port_channel(backend_channel, chan, dest_addr, dest_port)
                
            except Exception as e:
                logger.error(f"Failed to open forwarded-tcpip: {e}, traceback:", exc_info=True)
                backend_channel.close()
            
        except Exception as e:
            logger.error(f"Reverse forward channel error: {e}")
            backend_channel.close()
    
    def forward_port_channel(self, client_channel, backend_channel, dest_addr, dest_port, transfer_id=None):
        """Forward data between port forwarding channels (no recording)"""
        bytes_sent = 0
        bytes_received = 0
        
        try:
            logger.info(f"Forwarding data for {dest_addr}:{dest_port}")
            
            while True:
                if client_channel.closed or backend_channel.closed:
                    break
                
                r, w, x = select.select([client_channel, backend_channel], [], [], 1.0)
                
                if client_channel in r:
                    data = client_channel.recv(4096)
                    if len(data) == 0:
                        break
                    backend_channel.send(data)
                    bytes_sent += len(data)
                
                if backend_channel in r:
                    data = backend_channel.recv(4096)
                    if len(data) == 0:
                        break
                    client_channel.send(data)
                    bytes_received += len(data)
        
        except Exception as e:
            logger.debug(f"Port forward channel ended: {e}")
        
        finally:
            logger.info(f"Closing forward channel for {dest_addr}:{dest_port} (sent={bytes_sent}, received={bytes_received})")
            
            # Update transfer stats in database
            if transfer_id:
                try:
                    self.update_transfer_stats(transfer_id, bytes_sent, bytes_received)
                except Exception as e:
                    logger.error(f"Failed to update transfer stats: {e}")
            
            try:
                if not client_channel.closed:
                    client_channel.close()
            except:
                pass
            try:
                if not backend_channel.closed:
                    backend_channel.close()
            except:
                pass
    
    def handle_pool_ip_to_localhost_forward(self, pool_ip, port, client_transport):
        """Forward connections from pool IP to client via SSH forwarded-tcpip channel
        
        Pool IP listener accepts connections (e.g. from backend) and opens 
        forwarded-tcpip channels to the client.
        
        Args:
            pool_ip: IP address from pool (e.g. 10.0.160.129)
            port: Port to forward
            client_transport: Client's SSH transport for opening channels
        """
        import socket
        
        try:
            # Create listening socket on pool IP
            listen_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            listen_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            listen_sock.bind((pool_ip, port))
            listen_sock.listen(5)
            listen_sock.settimeout(1.0)
            
            logger.info(f"Listening on {pool_ip}:{port}, forwarding via SSH to client")
            
            # Accept connections and forward to client via SSH channel
            while client_transport.is_active():
                try:
                    conn, conn_addr = listen_sock.accept()
                    logger.info(f"Connection from {conn_addr} to {pool_ip}:{port}")
                    
                    # Open forwarded-tcpip channel to client
                    # SSH protocol limitation: we don't know the actual destination from -R request
                    # We assume client used -R port:localhost:port (same port for bind and destination)
                    try:
                        client_channel = client_transport.open_channel(
                            'forwarded-tcpip',
                            ('localhost', port),  # Assumed destination - same port as bind
                            (conn_addr[0], conn_addr[1])  # Originator (who connected)
                        )
                        
                        logger.info(f"Opened forwarded-tcpip channel to client for {conn_addr}")
                        
                        # Relay data bidirectionally between socket and channel
                        def relay_socket_to_channel(sock, chan):
                            try:
                                while True:
                                    r, _, _ = select.select([sock, chan], [], [], 1.0)
                                    
                                    if sock in r:
                                        data = sock.recv(4096)
                                        if len(data) == 0:
                                            break
                                        chan.send(data)
                                    
                                    if chan in r:
                                        data = chan.recv(4096)
                                        if len(data) == 0:
                                            break
                                        sock.send(data)
                            except Exception as e:
                                logger.debug(f"Relay ended: {e}")
                            finally:
                                try:
                                    sock.close()
                                except:
                                    pass
                                try:
                                    chan.close()
                                except:
                                    pass
                        
                        relay_thread = threading.Thread(
                            target=relay_socket_to_channel,
                            args=(conn, client_channel),
                            daemon=True
                        )
                        relay_thread.start()
                        
                    except Exception as e:
                        logger.error(f"Failed to open channel to client: {e}")
                        conn.close()
                        
                except socket.timeout:
                    continue
                except Exception as e:
                    if client_transport.is_active():
                        logger.error(f"Accept error on {pool_ip}:{port}: {e}")
                    break
            
            logger.info(f"Pool IP listener on {pool_ip}:{port} exiting")
            listen_sock.close()
            
        except Exception as e:
            logger.error(f"Pool IP listener error on {pool_ip}:{port}: {e}", exc_info=True)
    
    def handle_cascaded_reverse_forward(self, client_transport, backend_transport, server_handler):
        """Handle cascaded -R forward: backend -> jump -> client
        
        When backend opens a forwarded channel to us (because someone connected
        to backend:port), we need to forward it to pool IP listener which will
        then open forwarded-tcpip channel to client.
        """
        try:
            logger.info("Cascaded reverse forward handler started")
            
            pool_ip = server_handler.dest_ip  # Get pool IP for this session
            
            while backend_transport.is_active() and client_transport.is_active():
                try:
                    # Accept channel from backend
                    backend_channel = backend_transport.accept(timeout=1.0)
                    
                    if backend_channel is None:
                        continue
                    
                    logger.info(f"Got cascaded -R channel from backend")
                    
                    # Get port info
                    if hasattr(server_handler, 'remote_forward_requests') and len(server_handler.remote_forward_requests) > 0:
                        dest_addr, dest_port = server_handler.remote_forward_requests[0]
                        
                        # Connect to pool IP listener (which will forward to client)
                        try:
                            import socket
                            jump_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                            jump_sock.connect((pool_ip, dest_port))
                            
                            logger.info(f"Connected to pool IP {pool_ip}:{dest_port}, forwarding data")
                            
                            # Forward data between backend channel and pool IP socket
                            def forward_cascade(backend_chan, local_sock):
                                try:
                                    while True:
                                        r, _, _ = select.select([backend_chan, local_sock], [], [], 1.0)
                                        
                                        if backend_chan in r:
                                            data = backend_chan.recv(4096)
                                            if len(data) == 0:
                                                break
                                            local_sock.send(data)
                                        
                                        if local_sock in r:
                                            data = local_sock.recv(4096)
                                            if len(data) == 0:
                                                break
                                            backend_chan.send(data)
                                except Exception as e:
                                    logger.debug(f"Cascade forward ended: {e}")
                                finally:
                                    try:
                                        local_sock.close()
                                    except:
                                        pass
                                    try:
                                        backend_chan.close()
                                    except:
                                        pass
                            
                            forward_thread = threading.Thread(
                                target=forward_cascade,
                                args=(backend_channel, jump_sock),
                                daemon=True
                            )
                            forward_thread.start()
                            
                        except Exception as e:
                            logger.error(f"Failed to connect to pool IP {pool_ip}:{dest_port}: {e}")
                            backend_channel.close()
                    else:
                        logger.error("No remote forward requests stored")
                        backend_channel.close()
                    
                except Exception as e:
                    if "timeout" not in str(e).lower():
                        logger.error(f"Cascade accept error: {e}")
            
            logger.info("Cascaded reverse forward handler exiting")
            
        except Exception as e:
            logger.error(f"Cascaded reverse forward error: {e}", exc_info=True)
    
    def handle_reverse_forward_on_backend_ip(self, client_transport, backend_ip, address, port):
        """Open socket listener on backend's IP address from pool
        
        For -R 9090:localhost:8080:
        - Client sends -R request
        - We open socket on backend_ip:9090 (e.g. 10.0.160.4:9090)
        - Backend connects to localhost:9090 (which resolves to 10.0.160.4:9090 via routing)
        - We forward connection to client via SSH
        - Client connects to its localhost:8080
        
        Args:
            client_transport: SSH transport to client
            backend_ip: IP address from pool assigned to this backend
            address: Bind address (usually '' or 'localhost')
            port: Port to bind
        """
        import socket
        
        try:
            # Create listening socket on backend's IP
            listen_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            listen_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            
            # Bind to backend IP (from pool) so backend can connect to it
            listen_sock.bind((backend_ip, port))
            listen_sock.listen(5)
            listen_sock.settimeout(1.0)
            
            logger.info(f"Listening on backend IP {backend_ip}:{port} for -R forward to client")
            
            # Accept connections while client is connected
            while client_transport.is_active():
                try:
                    conn, conn_addr = listen_sock.accept()
                    logger.info(f"Reverse forward connection from {conn_addr} to {backend_ip}:{port}")
                    
                    # Open channel to client - use direct-tcpip instead of forwarded-tcpip
                    # Client will connect to localhost:port
                    try:
                        # direct-tcpip: tell client to connect to destination
                        client_chan = client_transport.open_channel(
                            'direct-tcpip',
                            ('localhost', port),  # Destination on client
                            conn_addr  # Our address (source)
                        )
                        
                        logger.info(f"Opened direct-tcpip channel to client localhost:{port}, forwarding data")
                        
                        # Forward data between socket and SSH channel
                        def forward_socket_to_channel(sock, chan):
                            try:
                                while True:
                                    r, _, _ = select.select([sock, chan], [], [], 1.0)
                                    
                                    if sock in r:
                                        data = sock.recv(4096)
                                        if len(data) == 0:
                                            break
                                        chan.send(data)
                                    
                                    if chan in r:
                                        data = chan.recv(4096)
                                        if len(data) == 0:
                                            break
                                        sock.send(data)
                            except Exception as e:
                                logger.debug(f"Forward ended: {e}")
                            finally:
                                try:
                                    sock.close()
                                except:
                                    pass
                                try:
                                    chan.close()
                                except:
                                    pass
                        
                        forward_thread = threading.Thread(
                            target=forward_socket_to_channel,
                            args=(conn, client_chan),
                            daemon=True
                        )
                        forward_thread.start()
                        
                    except Exception as e:
                        logger.error(f"Failed to open channel to client: {e}")
                        conn.close()
                        
                except socket.timeout:
                    continue
                except Exception as e:
                    if client_transport.is_active():
                        logger.error(f"Accept error on {backend_ip}:{port}: {e}")
                    break
            
            logger.info(f"Reverse forward listener on {backend_ip}:{port} exiting")
            listen_sock.close()
            
        except Exception as e:
            logger.error(f"Reverse forward listener error on {backend_ip}:{port}: {e}", exc_info=True)
    
    def handle_backend_socket_forward(self, client_transport, backend_ip, address, port):
        """Open a socket listener on backend via SSH and forward to client
        
        This is a workaround for -R through proxy. We can't use SSH -R to backend
        because client doesn't know to accept the forwarded-tcpip channels.
        
        Instead, we:
        1. SSH to backend and run: nc -l -p 9090
        2. Accept connections  
        3. Forward each connection to client via forwarded-tcpip
        
        Actually, simpler: use SSH dynamic forward to create a listening port
        """
        import socket
        import paramiko
        
        try:
            # Connect to backend via SSH and open a remote tunnel
            logger.info(f"Opening socket listener on backend {backend_ip}:{port}")
            
            # Create SSH connection to backend
            backend_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            backend_sock.connect((backend_ip, 22))
            
            backend_trans = paramiko.Transport(backend_sock)
            backend_trans.start_client()
            
            # TODO: We need credentials here... this won't work without them
            # This approach is too complex
            
            logger.error("Backend socket forward not yet fully implemented")
            backend_trans.close()
            
        except Exception as e:
            logger.error(f"Backend socket forward error: {e}", exc_info=True)
    
    def handle_reverse_forwarding_v2(self, client_transport, backend_transport, server_handler):
        """Accept forwarded connections from backend and forward to client
        
        For -R 9090:localhost:8080:
        - Backend has port 9090 open
        - When someone connects, backend opens channel to us
        - We accept it and connect via socket to client's localhost:8080
        """
        try:
            logger.info("Reverse forwarding v2 handler started")
            
            # Build port mapping: we need to know which backend port maps to which client destination
            port_map = {}
            if hasattr(server_handler, 'remote_forward_requests'):
                for dest_addr, dest_port in server_handler.remote_forward_requests:
                    # For -R 9090:localhost:8080, backend port 9090 -> client localhost:8080
                    port_map[dest_port] = (dest_addr if dest_addr else 'localhost', dest_port)
                    logger.info(f"Port mapping: backend {dest_port} -> client {dest_addr}:{dest_port}")
            
            while backend_transport.is_active() and client_transport.is_active():
                try:
                    # Accept channel from backend
                    backend_channel = backend_transport.accept(timeout=1.0)
                    
                    if backend_channel is None:
                        continue
                    
                    # Get origin info from channel
                    origin = getattr(backend_channel, 'origin_addr', ('unknown', 0))
                    logger.info(f"Got reverse forward channel from backend, origin={origin}")
                    
                    # For now, if we only have one mapping, use it
                    if len(port_map) == 1:
                        dest_addr, dest_port = list(port_map.values())[0]
                        server_port = list(port_map.keys())[0]
                        logger.info(f"Forwarding to client {dest_addr}:{dest_port} (from backend port {server_port})")
                        
                        # Open forwarded-tcpip channel to client
                        # Parameters according to paramiko docs:
                        # - src_addr: (src_addr, src_port) of the incoming connection (origin)
                        # - dest_addr: (dest_addr, dest_port) of the forwarded server
                        try:
                            client_channel = client_transport.open_forwarded_tcpip_channel(
                                origin,  # Source: who connected to backend
                                ('', server_port)  # Dest: where backend was listening
                            )
                            
                            logger.info(f"Opened forwarded-tcpip channel to client, forwarding data")
                            
                            # Forward data
                            forward_thread = threading.Thread(
                                target=self.forward_port_channel,
                                args=(backend_channel, client_channel, dest_addr, dest_port),
                                daemon=True
                            )
                            forward_thread.start()
                            
                        except Exception as e:
                            logger.error(f"Failed to open channel to client: {e}")
                            backend_channel.close()
                    else:
                        logger.error(f"Multiple port mappings not yet supported: {port_map}")
                        backend_channel.close()
                    
                except Exception as e:
                    if "timeout" not in str(e).lower():
                        logger.error(f"Reverse accept error: {e}")
            
            logger.info("Reverse forwarding v2 handler exiting")
            
        except Exception as e:
            logger.error(f"Reverse forwarding v2 error: {e}", exc_info=True)
    
    def handle_reverse_forward_listener(self, client_transport, address, port, dest_addr, dest_port):
        """Listen on a port and forward connections to SSH client
        
        This implements the server side of SSH -R (remote forward).
        We open a socket, listen for connections, and for each connection
        we open a forwarded-tcpip channel to the client.
        
        Args:
            client_transport: SSH transport to client
            address: Address to bind ('', 'localhost', etc)
            port: Port to bind
            dest_addr: Destination address on client side (e.g. 'localhost')
            dest_port: Destination port on client side (e.g. 8080)
        """
        import socket
        
        try:
            # Create listening socket
            listen_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            listen_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            bind_addr = '0.0.0.0' if address == '' else address
            listen_sock.bind((bind_addr, port))
            listen_sock.listen(5)
            listen_sock.settimeout(1.0)  # Timeout for accept
            
            logger.info(f"Listening for reverse forward on {bind_addr}:{port} -> client {dest_addr}:{dest_port}")
            
            # Accept connections while client is connected
            while client_transport.is_active():
                try:
                    conn, conn_addr = listen_sock.accept()
                    logger.info(f"Reverse forward connection from {conn_addr}")
                    
                    # Open forwarded-tcpip channel to client
                    # Client will connect to dest_addr:dest_port locally
                    try:
                        # Use direct method to open channel
                        client_chan = client_transport.open_channel(
                            'forwarded-tcpip',
                            (dest_addr, dest_port),
                            conn_addr
                        )
                        
                        logger.info(f"Opened forwarded-tcpip to client for {dest_addr}:{dest_port}")
                        
                        # Forward data in background thread
                        def forward_socket_to_channel(sock, chan):
                            try:
                                while True:
                                    r, _, _ = select.select([sock, chan], [], [], 1.0)
                                    
                                    if sock in r:
                                        data = sock.recv(4096)
                                        if len(data) == 0:
                                            break
                                        chan.send(data)
                                    
                                    if chan in r:
                                        data = chan.recv(4096)
                                        if len(data) == 0:
                                            break
                                        sock.send(data)
                            except:
                                pass
                            finally:
                                sock.close()
                                chan.close()
                        
                        forward_thread = threading.Thread(
                            target=forward_socket_to_channel,
                            args=(conn, client_chan),
                            daemon=True
                        )
                        forward_thread.start()
                        
                    except Exception as e:
                        logger.error(f"Failed to open channel to client: {e}")
                        conn.close()
                        
                except socket.timeout:
                    continue
                except Exception as e:
                    if client_transport.is_active():
                        logger.error(f"Accept error: {e}")
                    break
            
            logger.info(f"Reverse forward listener on port {port} exiting")
            listen_sock.close()
            
        except Exception as e:
            logger.error(f"Reverse forward listener error: {e}", exc_info=True)
    
    def monitor_grant_expiry(self, channel, backend_channel, transport, backend_transport, 
                             grant_end_time, db_session_id, session_id):
        """Monitor grant expiry and send warnings, then disconnect when grant expires."""
        try:
            now = datetime.utcnow()
            remaining = (grant_end_time - now).total_seconds()
            
            logger.info(f"Session {session_id}: Grant expires in {remaining/60:.1f} minutes ({grant_end_time})")
            
            # Warning times (in seconds before expiry)
            warnings = [
                (300, "5 minutes"),  # 5 minutes
                (60, "1 minute"),    # 1 minute
            ]
            
            for warning_seconds, warning_text in warnings:
                if remaining > warning_seconds:
                    # Sleep until warning time
                    sleep_time = remaining - warning_seconds
                    logger.debug(f"Session {session_id}: Sleeping {sleep_time:.0f}s until {warning_text} warning")
                    time.sleep(sleep_time)
                    
                    # Check if session is still active
                    if not transport.is_active() or not backend_transport.is_active():
                        logger.info(f"Session {session_id}: Already disconnected before {warning_text} warning")
                        return
                    
                    # Send wall-style warning
                    now = datetime.utcnow()
                    remaining = (grant_end_time - now).total_seconds()
                    if remaining > 0:
                        message = (
                            f"\r\n\r\n"
                            f"{'='*70}\r\n"
                            f"  *** WARNING: Your access grant expires in {warning_text} ***\r\n"
                            f"  Your session will be automatically disconnected at {grant_end_time} UTC\r\n"
                            f"{'='*70}\r\n\r\n"
                        )
                        try:
                            channel.send(message.encode())
                            logger.info(f"Session {session_id}: Sent {warning_text} warning")
                        except Exception as e:
                            logger.error(f"Session {session_id}: Failed to send warning: {e}")
                            return
                    
                    remaining = (grant_end_time - now).total_seconds()
            
            # Sleep until expiry
            if remaining > 0:
                logger.debug(f"Session {session_id}: Sleeping {remaining:.0f}s until grant expiry")
                time.sleep(remaining)
            
            # Check if session is still active
            if not transport.is_active() or not backend_transport.is_active():
                logger.info(f"Session {session_id}: Already disconnected before grant expiry")
                return
            
            # Send final disconnection message
            final_message = (
                f"\r\n\r\n"
                f"{'='*70}\r\n"
                f"  *** Your access grant has expired ***\r\n"
                f"  Disconnecting now...\r\n"
                f"{'='*70}\r\n\r\n"
            )
            try:
                channel.send(final_message.encode())
                time.sleep(1)  # Give time for message to be sent
            except:
                pass
            
            logger.info(f"Session {session_id}: Grant expired, closing connection")
            
            # Close channels and transports
            try:
                backend_channel.close()
            except:
                pass
            
            try:
                channel.close()
            except:
                pass
            
            try:
                backend_transport.close()
            except:
                pass
            
            try:
                transport.close()
            except:
                pass
            
            # Update database session
            db = SessionLocal()
            try:
                db_sess = db.query(DBSession).filter(DBSession.id == db_session_id).first()
                if db_sess and db_sess.is_active:
                    db_sess.ended_at = datetime.utcnow()
                    db_sess.is_active = False
                    db_sess.duration_seconds = int((db_sess.ended_at - db_sess.started_at).total_seconds())
                    db_sess.termination_reason = 'grant_expired'
                    db.commit()
                    logger.info(f"Session {session_id}: Updated database with termination_reason='grant_expired'")
            except Exception as e:
                logger.error(f"Session {session_id}: Failed to update database: {e}")
            finally:
                db.close()
                
        except Exception as e:
            logger.error(f"Session {session_id}: Error in grant expiry monitor: {e}", exc_info=True)
    
    def log_scp_transfer(self, db_session_id, command, direction):
        """Log SCP file transfer"""
        try:
            # Parse SCP command: scp [-r] [-t|-f] [file]
            # -t = to (upload), -f = from (download)
            import re
            
            # Extract file path from command
            match = re.search(r'scp\s+(?:-\w+\s+)*([^\s]+)', command)
            if not match:
                return
            
            file_path = match.group(1)
            
            db = SessionLocal()
            try:
                transfer = SessionTransfer(
                    session_id=db_session_id,
                    transfer_type=f'scp_{direction}',
                    file_path=file_path,
                    started_at=datetime.utcnow()
                )
                db.add(transfer)
                db.commit()
                logger.info(f"Logged SCP {direction}: {file_path}")
            finally:
                db.close()
        except Exception as e:
            logger.error(f"Failed to log SCP transfer: {e}")
    
    def log_sftp_transfer(self, db_session_id):
        """Log SFTP transfer session (without individual file details)"""
        try:
            db = SessionLocal()
            try:
                transfer = SessionTransfer(
                    session_id=db_session_id,
                    transfer_type='sftp_session',
                    started_at=datetime.utcnow()
                )
                db.add(transfer)
                db.commit()
                db.refresh(transfer)
                logger.info(f"Started SFTP transfer tracking (ID: {transfer.id})")
                return transfer.id
            finally:
                db.close()
        except Exception as e:
            logger.error(f"Failed to log SFTP transfer: {e}")
            return None
    
    def log_port_forward(self, db_session_id, forward_type, local_addr, local_port, remote_addr, remote_port):
        """Log port forwarding channel"""
        try:
            db = SessionLocal()
            try:
                transfer = SessionTransfer(
                    session_id=db_session_id,
                    transfer_type=forward_type,
                    local_addr=local_addr,
                    local_port=local_port,
                    remote_addr=remote_addr,
                    remote_port=remote_port,
                    started_at=datetime.utcnow()
                )
                db.add(transfer)
                db.commit()
                db.refresh(transfer)
                logger.info(f"Logged {forward_type}: {local_addr}:{local_port} -> {remote_addr}:{remote_port}")
                return transfer.id
            finally:
                db.close()
        except Exception as e:
            logger.error(f"Failed to log port forward: {e}")
            return None
    
    def log_socks_connection(self, db_session_id, remote_addr, remote_port):
        """Log SOCKS proxy connection"""
        try:
            db = SessionLocal()
            try:
                transfer = SessionTransfer(
                    session_id=db_session_id,
                    transfer_type='socks_connection',
                    remote_addr=remote_addr,
                    remote_port=remote_port,
                    started_at=datetime.utcnow()
                )
                db.add(transfer)
                db.commit()
                db.refresh(transfer)
                logger.info(f"Logged SOCKS connection: {remote_addr}:{remote_port}")
                return transfer.id
            finally:
                db.close()
        except Exception as e:
            logger.error(f"Failed to log SOCKS connection: {e}")
            return None
    
    def update_transfer_stats(self, transfer_id, bytes_sent, bytes_received):
        """Update transfer statistics"""
        try:
            db = SessionLocal()
            try:
                transfer = db.query(SessionTransfer).filter(SessionTransfer.id == transfer_id).first()
                if transfer:
                    transfer.bytes_sent = (transfer.bytes_sent or 0) + bytes_sent
                    transfer.bytes_received = (transfer.bytes_received or 0) + bytes_received
                    transfer.ended_at = datetime.utcnow()
                    db.commit()
            finally:
                db.close()
        except Exception as e:
            logger.error(f"Failed to update transfer stats: {e}")
    
    def handle_client(self, client_socket, client_addr):
        """Handle incoming client connection"""
        source_ip = client_addr[0]
        
        # NEW: Extract destination IP (the IP client connected to)
        dest_ip = client_socket.getsockname()[0]
        
        session_id = f"{source_ip}_{datetime.now().timestamp()}"
        
        logger.info(f"New connection from {source_ip} to {dest_ip}")
        
        db = SessionLocal()
        backend_transport = None
        
        try:
            # Setup SSH transport for client
            transport = paramiko.Transport(client_socket)
            transport.add_server_key(self.host_key)
            
            # Create server handler with source and dest IPs
            server_handler = SSHProxyHandler(source_ip, dest_ip, db)
            transport.start_server(server=server_handler)
            
            # Wait for authentication
            channel = transport.accept(20)
            if channel is None:
                logger.warning(f"No channel opened from {source_ip}")
                # If no_grant_reason is set, banner was already shown
                if server_handler.no_grant_reason:
                    logger.info(f"Connection rejected due to no grant: {server_handler.no_grant_reason}")
                return
            
            # Get authenticated user and target server
            if not server_handler.authenticated_user or not server_handler.target_server:
                logger.error("Authentication failed or no target server")
                channel.close()
                return
            
            user = server_handler.authenticated_user
            target_server = server_handler.target_server
            
            # Connect to backend server via SSH
            logger.info(f"Connecting to backend: {target_server.ip_address}:22")
            backend_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            backend_socket.connect((target_server.ip_address, 22))
            
            backend_transport = paramiko.Transport(backend_socket)
            backend_transport.start_client()
            
            # Note: Agent will be created when needed (after channel requests are processed)
            
            # Authenticate to backend using client credentials
            try:
                authenticated = False
                
                # If client used pubkey, REQUIRE agent forwarding
                if server_handler.client_key:
                    if not server_handler.agent_channel:
                        # No agent forwarding - show hint
                        logger.info("Pubkey but no agent forwarding")
                        channel.send(f"ERROR: Public key authentication requires agent forwarding.\r\n".encode())
                        channel.send(f"Try: ssh -A {server_handler.ssh_login}@{server_handler.dest_ip}\r\n".encode())
                        channel.send(f"Or:  ssh -o PubkeyAuthentication=no {server_handler.ssh_login}@{server_handler.dest_ip}\r\n".encode())
                        channel.close()
                        return
                    
                    # Try agent forwarding
                    logger.info("Using forwarded agent for backend")
                    try:
                        from paramiko.agent import AgentServerProxy
                        agent = AgentServerProxy(transport)
                        agent.connect()
                        agent_keys = agent.get_keys()
                        logger.info(f"Got {len(agent_keys)} keys from agent")
                        
                        for key in agent_keys:
                            try:
                                backend_transport.auth_publickey(server_handler.ssh_login, key)
                                logger.info(f"Backend auth with agent succeeded")
                                authenticated = True
                                break
                            except Exception as e:
                                logger.debug(f"Agent key failed: {e}")
                                continue
                        
                        if not authenticated:
                            # No agent keys worked
                            logger.info("No agent keys worked")
                            channel.send(f"ERROR: None of your SSH keys are authorized on the backend server.\r\n".encode())
                            channel.send(f"Try: ssh -o PubkeyAuthentication=no {server_handler.ssh_login}@{server_handler.dest_ip}\r\n".encode())
                            channel.close()
                            return
                    except Exception as e:
                        logger.info(f"Agent error: {e}")
                        channel.send(f"ERROR: Agent forwarding failed: {e}\r\n".encode())
                        channel.send(f"Try: ssh -o PubkeyAuthentication=no {server_handler.ssh_login}@{server_handler.dest_ip}\r\n".encode())
                        channel.close()
                        return
                
                # If client used password, use it
                elif server_handler.client_password:
                    try:
                        backend_transport.auth_password(server_handler.ssh_login, server_handler.client_password)
                        logger.info(f"Backend auth with password succeeded")
                        authenticated = True
                    except Exception as e:
                        logger.error(f"Backend password auth failed: {e}")
                        channel.send(b"ERROR: Password failed on backend.\r\n")
                        channel.close()
                        return
                else:
                    channel.close()
                    return
                    
            except Exception as e:
                logger.error(f"Backend auth error: {e}")
                channel.send(b"ERROR: Backend authentication error\r\n")
                channel.close()
                return
            
            # For -R (remote forward): Open listener on pool IP and forward to client
            # 
            # Flow: Backend localhost:9090 -> Jump(pool-ip):9090 -> Client localhost:8080
            # 
            # 1. Backend has -R 9090:localhost:9090 which forwards to jump pool IP
            # 2. Jump listens on pool IP (e.g. 10.0.160.129:9090)
            # 3. Jump opens forwarded-tcpip channel to client
            # 4. Client forwards to their localhost:8080 (as specified in -R 9090:localhost:8080)
            if hasattr(server_handler, 'remote_forward_requests'):
                pool_ip = server_handler.dest_ip  # IP from pool
                for address, port in server_handler.remote_forward_requests:
                    # Start listener on pool IP
                    listener_thread = threading.Thread(
                        target=self.handle_pool_ip_to_localhost_forward,
                        args=(pool_ip, port, transport),
                        daemon=True
                    )
                    listener_thread.start()
                    logger.info(f"Started -R listener on pool IP {pool_ip}:{port} -> client")
                    
                    # Also ask backend to forward to jump host
                    try:
                        bound_port = backend_transport.request_port_forward(address, port)
                        logger.info(f"Cascaded -R: backend:{bound_port} -> jump:{port}")
                    except Exception as e:
                        logger.error(f"Failed to setup cascaded -R for port {port}: {e}")
            
            # Open backend channel
            backend_channel = backend_transport.open_session()
            
            # Start port forwarding handler in background thread
            # This will handle any -L/-R/-D requests from client
            forward_thread = threading.Thread(
                target=self.handle_port_forwarding,
                args=(transport, backend_transport, server_handler, user, target_server),
                daemon=True
            )
            forward_thread.start()
            logger.info("Port forwarding handler started")
            
            # For cascaded -R, accept channels from backend and forward to client
            if hasattr(server_handler, 'remote_forward_requests'):
                cascade_thread = threading.Thread(
                    target=self.handle_cascaded_reverse_forward,
                    args=(transport, backend_transport, server_handler),
                    daemon=True
                )
                cascade_thread.start()
                logger.info("Cascaded reverse forward handler started")
            
            # Setup PTY if client requested it (for interactive sessions)
            if server_handler.pty_term:
                logger.info(f"Setting backend PTY: {server_handler.pty_term} {server_handler.pty_width}x{server_handler.pty_height}")
                # Decode term if it's bytes
                term = server_handler.pty_term.decode('utf-8') if isinstance(server_handler.pty_term, bytes) else server_handler.pty_term
                backend_channel.get_pty(
                    term=term,
                    width=server_handler.pty_width,
                    height=server_handler.pty_height
                )
            
            # Invoke shell, exec command, or subsystem based on client request
            if server_handler.channel_type == 'exec' and server_handler.exec_command:
                # For SCP and other exec commands
                cmd_str = server_handler.exec_command.decode('utf-8') if isinstance(server_handler.exec_command, bytes) else server_handler.exec_command
                logger.info(f"Executing command on backend: {cmd_str}")
                backend_channel.exec_command(cmd_str)
            elif server_handler.channel_type == 'subsystem' and server_handler.subsystem_name:
                # For SFTP and other subsystems
                subsys_name = server_handler.subsystem_name.decode('utf-8') if isinstance(server_handler.subsystem_name, bytes) else server_handler.subsystem_name
                logger.info(f"Invoking subsystem on backend: {subsys_name}")
                backend_channel.invoke_subsystem(subsys_name)
                
                # For SFTP, we'll log transfers by monitoring data flow
                # Note: Full SFTP parsing would require decoding the binary protocol
                if subsys_name == 'sftp':
                    logger.info(f"SFTP subsystem started - transfers will be logged")
            else:
                # For interactive shell sessions
                backend_channel.invoke_shell()
            
            # Determine if we should record this session
            # SCP/SFTP sessions should NOT be recorded (only tracked in SessionTransfer)
            should_record = True
            if server_handler.channel_type == 'exec' and server_handler.exec_command:
                cmd_str = server_handler.exec_command.decode('utf-8') if isinstance(server_handler.exec_command, bytes) else server_handler.exec_command
                if 'scp' in cmd_str:
                    should_record = False
                    logger.info(f"SCP session detected - disabling recording, will track in transfers only")
            elif server_handler.channel_type == 'subsystem' and server_handler.subsystem_name:
                subsys = server_handler.subsystem_name.decode('utf-8') if isinstance(server_handler.subsystem_name, bytes) else server_handler.subsystem_name
                if subsys == 'sftp':
                    should_record = False
                    logger.info(f"SFTP session detected - disabling recording, will track in transfers only")
            
            # Start session recording (only for interactive sessions)
            recorder = None
            if should_record:
                recorder = SSHSessionRecorder(session_id, user.username, target_server.ip_address)
                recorder.record_event('session_start', f"User {user.username} connecting to {target_server.ip_address}")
            
            # Create session record in database
            db_session = DBSession(
                session_id=session_id,
                user_id=user.id,
                server_id=target_server.id,
                protocol='ssh',
                source_ip=source_ip,
                proxy_ip=dest_ip,
                backend_ip=target_server.ip_address,
                backend_port=22,
                ssh_username=server_handler.ssh_login,
                subsystem_name=server_handler.subsystem_name.decode('utf-8') if server_handler.subsystem_name and isinstance(server_handler.subsystem_name, bytes) else server_handler.subsystem_name,
                ssh_agent_used=bool(server_handler.agent_channel),
                started_at=datetime.utcnow(),
                is_active=True,
                recording_path=recorder.recording_file if recorder and hasattr(recorder, 'recording_file') else None
            )
            db.add(db_session)
            db.commit()
            db.refresh(db_session)
            logger.info(f"Session {session_id} tracked in database (ID: {db_session.id})")
            
            # Pass db_session to server_handler for port forwarding logging
            server_handler.db_session = db_session
            
            # Log SCP transfers (now that we have db_session.id)
            if server_handler.channel_type == 'exec' and server_handler.exec_command:
                cmd_str = server_handler.exec_command.decode('utf-8') if isinstance(server_handler.exec_command, bytes) else server_handler.exec_command
                if 'scp' in cmd_str:
                    if '-t' in cmd_str:
                        # SCP upload (to server)
                        self.log_scp_transfer(db_session.id, cmd_str, 'upload')
                    elif '-f' in cmd_str:
                        # SCP download (from server)
                        self.log_scp_transfer(db_session.id, cmd_str, 'download')
            
            # Write to utmp/wtmp (makes session visible in 'w' command)
            tty_name = f"ssh{db_session.id % 100}"  # ssh0-ssh99
            backend_display = f"{server_handler.ssh_login}@{target_server.name}"
            if server_handler.subsystem_name:
                subsys = server_handler.subsystem_name.decode('utf-8') if isinstance(server_handler.subsystem_name, bytes) else server_handler.subsystem_name
                backend_display += f":{subsys}"
            write_utmp_login(session_id, user.username, tty_name, source_ip, backend_display)
            logger.info(f"Session {session_id} registered in utmp as {tty_name}")
            
            # Check grant expiry for interactive shell sessions
            grant_end_time = None
            if server_handler.channel_type == 'shell' and server_handler.matching_policies:
                # Use effective_end_time from access control if available
                # This considers both policy end_time AND schedule window end
                if hasattr(server_handler, 'access_result') and server_handler.access_result:
                    grant_end_time = server_handler.access_result.get('effective_end_time')
                
                # Fallback to old behavior (earliest policy end_time)
                if grant_end_time is None:
                    end_times = [p.end_time for p in server_handler.matching_policies if p.end_time]
                    if end_times:
                        grant_end_time = min(end_times)
                
                if grant_end_time:
                    logger.info(f"Session {session_id}: Grant expires at {grant_end_time}")
                    
                    # Send welcome message
                    now = datetime.utcnow()
                    remaining = grant_end_time - now
                    remaining_seconds = remaining.total_seconds()
                    
                    # Format time remaining - show minutes if < 1 hour, else show hours
                    if remaining_seconds < 3600:
                        time_str = f"{remaining_seconds/60:.1f} minutes"
                    else:
                        time_str = f"{remaining_seconds/3600:.1f} hours"
                    
                    # Convert UTC to Europe/Warsaw for display
                    warsaw_tz = pytz.timezone('Europe/Warsaw')
                    grant_end_time_local = pytz.utc.localize(grant_end_time).astimezone(warsaw_tz)
                    
                    welcome_msg = (
                        f"\r\n"
                        f"{'='*70}\r\n"
                        f"  Access Grant Information\r\n"
                        f"  Your access expires at: {grant_end_time_local.strftime('%Y-%m-%d %H:%M:%S %Z')}\r\n"
                        f"  Time remaining: {time_str}\r\n"
                        f"  \r\n"
                        f"  You will receive warnings before your access expires.\r\n"
                        f"  Your session will be automatically disconnected at expiry time.\r\n"
                        f"{'='*70}\r\n\r\n"
                    )
                    
                    try:
                        channel.send(welcome_msg.encode())
                        logger.info(f"Session {session_id}: Sent grant expiry welcome message")
                    except Exception as e:
                        logger.error(f"Session {session_id}: Failed to send welcome message: {e}")
                    
                    # Start grant expiry monitor thread
                    monitor_thread = threading.Thread(
                        target=self.monitor_grant_expiry,
                        args=(channel, backend_channel, transport, backend_transport, 
                              grant_end_time, db_session.id, session_id),
                        daemon=True
                    )
                    monitor_thread.start()
                    logger.info(f"Session {session_id}: Started grant expiry monitor thread")
            
            # Forward traffic (with SFTP tracking if applicable)
            is_sftp = (server_handler.channel_type == 'subsystem' and 
                      server_handler.subsystem_name and 
                      (server_handler.subsystem_name.decode('utf-8') if isinstance(server_handler.subsystem_name, bytes) else server_handler.subsystem_name) == 'sftp')
            self.forward_channel(channel, backend_channel, recorder, db_session.id, is_sftp)
            
            # Close session in database
            db_session.ended_at = datetime.utcnow()
            db_session.is_active = False
            db_session.duration_seconds = int((db_session.ended_at - db_session.started_at).total_seconds())
            db_session.termination_reason = 'normal'
            if recorder and hasattr(recorder, 'recording_file') and os.path.exists(recorder.recording_file):
                db_session.recording_size = os.path.getsize(recorder.recording_file)
            db.commit()
            logger.info(f"Session {session_id} ended normally (duration: {db_session.duration_seconds}s)")
            
            # Write logout to utmp/wtmp
            write_utmp_logout(tty_name, user.username)
            logger.info(f"Session {session_id} removed from utmp")
            
            # Save recording (only if we were recording)
            if recorder:
                recorder.record_event('session_end', 'Connection closed')
                recorder.save()
        
        except Exception as e:
            logger.error(f"Error handling client {source_ip}: {e}", exc_info=True)
            # Try to close session in database on error
            try:
                db_session_error = db.query(DBSession).filter(DBSession.session_id == session_id).first()
                if db_session_error and db_session_error.is_active:
                    db_session_error.ended_at = datetime.utcnow()
                    db_session_error.is_active = False
                    db_session_error.duration_seconds = int((db_session_error.ended_at - db_session_error.started_at).total_seconds())
                    db_session_error.termination_reason = 'error'
                    db.commit()
                    logger.info(f"Session {session_id} closed due to error")
                    
                    # Write logout to utmp
                    tty_name = f"ssh{db_session_error.id % 100}"
                    write_utmp_logout(tty_name, user.username if 'user' in locals() else "")
                    
            except Exception as cleanup_error:
                logger.error(f"Error closing session record: {cleanup_error}")
        
        finally:
            if backend_transport:
                backend_transport.close()
            db.close()
            client_socket.close()
    
    def start(self):
        """Start the proxy server"""
        logger.info(f"Starting SSH Proxy Server on {self.host}:{self.port}")
        
        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server_socket.bind((self.host, self.port))
        server_socket.listen(100)
        
        logger.info(f"SSH Proxy listening on {self.host}:{self.port}")
        
        try:
            while True:
                client_socket, client_addr = server_socket.accept()
                client_thread = threading.Thread(
                    target=self.handle_client,
                    args=(client_socket, client_addr)
                )
                client_thread.daemon = True
                client_thread.start()
        
        except KeyboardInterrupt:
            logger.info("Shutting down SSH Proxy Server...")
        
        finally:
            server_socket.close()


def cleanup_stale_sessions():
    """Clean up active sessions from previous runs on startup"""
    try:
        from src.core.database import SessionLocal, Session
        from datetime import datetime
        
        db = SessionLocal()
        try:
            # Find all active sessions (is_active=True or ended_at=NULL)
            stale_sessions = db.query(Session).filter(
                (Session.is_active == True) | (Session.ended_at == None)
            ).all()
            
            if stale_sessions:
                now = datetime.utcnow()
                for session in stale_sessions:
                    session.is_active = False
                    session.ended_at = now
                    session.termination_reason = 'service_restart'
                    
                    # Calculate duration if we have start time
                    if session.started_at:
                        session.duration_seconds = int((now - session.started_at).total_seconds())
                
                db.commit()
                logger.info(f"Cleaned up {len(stale_sessions)} stale sessions from previous run")
            else:
                logger.info("No stale sessions to clean up")
        finally:
            db.close()
    except Exception as e:
        logger.error(f"Failed to clean up stale sessions: {e}")


def main():
    """Main entry point"""
    # Clean up stale sessions from previous runs
    cleanup_stale_sessions()
    
    proxy = SSHProxyServer(host='0.0.0.0', port=22)  # Listen on all interfaces
    proxy.start()


if __name__ == '__main__':
    main()

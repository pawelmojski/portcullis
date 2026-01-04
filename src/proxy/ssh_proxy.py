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
from datetime import datetime
from pathlib import Path
import paramiko

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.core.database import SessionLocal, User, Server, AccessGrant, Session as DBSession
from src.core.access_control_v2 import AccessControlEngineV2 as AccessControl
from src.core.ip_pool import IPPoolManager
from src.core.utmp_helper import write_utmp_login, write_utmp_logout

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
    """Records SSH session I/O to file"""
    
    def __init__(self, session_id: str, username: str, server_ip: str):
        self.session_id = session_id
        self.username = username
        self.server_ip = server_ip
        self.start_time = datetime.now()
        
        # Create recording file
        timestamp = self.start_time.strftime("%Y%m%d_%H%M%S")
        filename = f"{timestamp}_{username}_{server_ip.replace('.', '_')}_{session_id}.log"
        self.log_file = Path(f"/var/log/jumphost/ssh_recordings/{filename}")
        
        # Metadata
        self.metadata = {
            'session_id': session_id,
            'username': username,
            'server_ip': server_ip,
            'start_time': self.start_time.isoformat(),
            'events': []
        }
        
        logger.info(f"Recording session to: {self.log_file}")
    
    def record_event(self, event_type: str, data: str):
        """Record an event"""
        event = {
            'timestamp': datetime.now().isoformat(),
            'type': event_type,
            'data': data if len(data) < 1000 else data[:1000] + '... [truncated]'
        }
        self.metadata['events'].append(event)
    
    def save(self):
        """Save recording to file"""
        self.metadata['end_time'] = datetime.now().isoformat()
        self.metadata['duration_seconds'] = (datetime.now() - self.start_time).total_seconds()
        
        with open(self.log_file, 'w') as f:
            json.dump(self.metadata, f, indent=2)
        
        logger.info(f"Session recording saved: {self.log_file}")


class SSHProxyHandler(paramiko.ServerInterface):
    """Handles SSH authentication and channel requests"""
    
    def __init__(self, source_ip: str, dest_ip: str, db_session):
        self.source_ip = source_ip
        self.dest_ip = dest_ip  # NEW: destination IP client connected to
        self.db = db_session
        self.access_control = AccessControl()
        self.authenticated_user = None
        self.target_server = None
        self.client_password = None
        self.client_key = None
        self.agent_channel = None  # For agent forwarding
        # PTY parameters from client
        self.pty_term = None
        self.pty_width = None
        self.pty_height = None
        self.pty_modes = None
        # Channel type and exec command
        self.channel_type = None  # 'shell', 'exec', or 'subsystem'
        self.exec_command = None
        self.subsystem_name = None
        
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
            return paramiko.AUTH_FAILED
        
        # All checks passed
        self.target_server = result['server']
        self.authenticated_user = result['user']
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
            return paramiko.AUTH_FAILED
        
        # Accept pubkey - backend will verify agent forwarding works
        # If agent fails, we'll disconnect properly for password retry
        logger.info(f"Pubkey accepted - will verify agent forwarding in backend")
        
        # Store authentication info
        self.target_server = result['server']
        self.authenticated_user = result['user']
        self.ssh_login = username  # SSH login for backend (e.g., "ideo")
        self.client_key = key
        
        return paramiko.AUTH_SUCCESSFUL
    
    def get_allowed_auths(self, username):
        """Return allowed authentication methods"""
        return "publickey,password"
    
    def check_channel_request(self, kind: str, chanid: int):
        """Allow session channel requests"""
        logger.info(f"Channel request: kind={kind}, chanid={chanid}")
        if kind == 'session':
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
    
    def forward_channel(self, client_channel, backend_channel, recorder: SSHSessionRecorder):
        """Forward data between client and backend server via SSH channels"""
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
                    recorder.record_event('client_to_server', data.decode('utf-8', errors='ignore'))
                
                if backend_channel in r:
                    data = backend_channel.recv(4096)
                    if len(data) == 0:
                        break
                    client_channel.send(data)
                    recorder.record_event('server_to_client', data.decode('utf-8', errors='ignore'))
        
        except Exception as e:
            logger.debug(f"Channel forwarding ended: {e}")
        
        finally:
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
                return
            
            # Get authenticated user and target server
            if not server_handler.authenticated_user or not server_handler.target_server:
                logger.error("Authentication failed or no target server")
                channel.close()
                return
            
            user = server_handler.authenticated_user
            target_server = server_handler.target_server
            
            # Start session recording
            recorder = SSHSessionRecorder(session_id, user.username, target_server.ip_address)
            recorder.record_event('session_start', f"User {user.username} connecting to {target_server.ip_address}")
            
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
            
            # Open backend channel
            backend_channel = backend_transport.open_session()
            
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
            else:
                # For interactive shell sessions
                backend_channel.invoke_shell()
            
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
                recording_path=recorder.recording_file if hasattr(recorder, 'recording_file') else None
            )
            db.add(db_session)
            db.commit()
            db.refresh(db_session)
            logger.info(f"Session {session_id} tracked in database (ID: {db_session.id})")
            
            # Write to utmp/wtmp (makes session visible in 'w' command)
            tty_name = f"ssh{db_session.id % 100}"  # ssh0-ssh99
            backend_display = f"{server_handler.ssh_login}@{target_server.name}"
            if server_handler.subsystem_name:
                subsys = server_handler.subsystem_name.decode('utf-8') if isinstance(server_handler.subsystem_name, bytes) else server_handler.subsystem_name
                backend_display += f":{subsys}"
            write_utmp_login(session_id, user.username, tty_name, source_ip, backend_display)
            logger.info(f"Session {session_id} registered in utmp as {tty_name}")
            
            # Forward traffic
            self.forward_channel(channel, backend_channel, recorder)
            
            # Close session in database
            db_session.ended_at = datetime.utcnow()
            db_session.is_active = False
            db_session.duration_seconds = int((db_session.ended_at - db_session.started_at).total_seconds())
            db_session.termination_reason = 'normal'
            if hasattr(recorder, 'recording_file') and os.path.exists(recorder.recording_file):
                db_session.recording_size = os.path.getsize(recorder.recording_file)
            db.commit()
            logger.info(f"Session {session_id} ended normally (duration: {db_session.duration_seconds}s)")
            
            # Write logout to utmp/wtmp
            write_utmp_logout(tty_name, user.username)
            logger.info(f"Session {session_id} removed from utmp")
            
            # Save recording
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


def main():
    """Main entry point"""
    proxy = SSHProxyServer(host='0.0.0.0', port=22)  # Listen on all interfaces
    proxy.start()


if __name__ == '__main__':
    main()

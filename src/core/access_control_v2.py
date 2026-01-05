"""Access Control Engine V2 - New flexible policy-based system."""
from datetime import datetime
from typing import Optional, List, Dict
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_
import logging

from .database import (
    User, Server, AccessGrant, AuditLog, IPAllocation,
    UserSourceIP, ServerGroup, ServerGroupMember, AccessPolicy, PolicySSHLogin,
    UserGroup, UserGroupMember, get_all_user_groups, get_all_server_groups
)

logger = logging.getLogger(__name__)


class AccessControlEngineV2:
    """New flexible policy-based access control system."""
    
    def find_backend_by_proxy_ip(
        self,
        db: Session,
        proxy_ip: str
    ) -> Optional[Dict]:
        """
        Find backend server by proxy IP address (destination IP).
        
        Looks up in ip_allocations table to find which backend server
        is assigned to this proxy IP.
        
        Args:
            db: Database session
            proxy_ip: Destination IP that client connected to
            
        Returns:
            Dict with server info or None if not found
            {
                'server': Server object,
                'allocation': IPAllocation object
            }
        """
        try:
            allocation = db.query(IPAllocation).filter(
                and_(
                    IPAllocation.allocated_ip == proxy_ip,
                    IPAllocation.is_active == True
                )
            ).first()
            
            if not allocation:
                logger.warning(f"No active IP allocation found for proxy IP {proxy_ip}")
                return None
            
            server = db.query(Server).filter(
                Server.id == allocation.server_id,
                Server.is_active == True
            ).first()
            
            if not server:
                logger.error(f"Server ID {allocation.server_id} not found or inactive for IP {proxy_ip}")
                return None
            
            logger.info(f"Proxy IP {proxy_ip} maps to backend server {server.ip_address} (ID: {server.id})")
            return {
                'server': server,
                'allocation': allocation
            }
            
        except Exception as e:
            logger.error(f"Error looking up backend for proxy IP {proxy_ip}: {e}", exc_info=True)
            return None
    
    def check_access_v2(
        self,
        db: Session,
        source_ip: str,
        dest_ip: str,
        protocol: str,
        ssh_login: Optional[str] = None
    ) -> dict:
        """
        New flexible policy-based access control.
        
        Args:
            db: Database session
            source_ip: Client's source IP address
            dest_ip: Destination proxy IP (to identify target server)
            protocol: 'ssh' or 'rdp'
            ssh_login: SSH login name (only for SSH protocol)
            
        Returns:
            dict with:
                - has_access: bool
                - user: User object or None
                - user_ip: UserSourceIP object or None
                - server: Server object or None
                - policies: List of matching AccessPolicy objects
                - reason: str explaining decision
        """
        try:
            # Step 1: Find user by source_ip
            user_ip = db.query(UserSourceIP).filter(
                UserSourceIP.source_ip == source_ip,
                UserSourceIP.is_active == True
            ).first()
            
            if not user_ip:
                logger.warning(f"Access denied: Unknown source IP {source_ip}")
                return {
                    'has_access': False,
                    'user': None,
                    'user_ip': None,
                    'server': None,
                    'policies': [],
                    'reason': f'Unknown source IP {source_ip}'
                }
            
            user = db.query(User).filter(
                User.id == user_ip.user_id,
                User.is_active == True
            ).first()
            
            if not user:
                logger.warning(f"Access denied: User ID {user_ip.user_id} not found or inactive")
                return {
                    'has_access': False,
                    'user': None,
                    'user_ip': user_ip,
                    'server': None,
                    'policies': [],
                    'reason': f'User not found or inactive'
                }
            
            # Step 2: Find backend server by dest_ip
            backend_info = self.find_backend_by_proxy_ip(db, dest_ip)
            if not backend_info:
                logger.warning(f"Access denied: No backend found for destination IP {dest_ip}")
                return {
                    'has_access': False,
                    'user': user,
                    'user_ip': user_ip,
                    'server': None,
                    'policies': [],
                    'reason': f'No backend server for destination IP {dest_ip}'
                }
            
            server = backend_info['server']
            
            # Step 3: Find matching policies with PRIORITY: user > group
            now = datetime.utcnow()
            
            # Get all server groups (including parent groups)
            server_group_ids = get_all_server_groups(server.id, db)
            
            # PRIORITY 1: Check for direct user policies first
            user_policies_query = db.query(AccessPolicy).filter(
                AccessPolicy.user_id == user.id,
                AccessPolicy.is_active == True,
                AccessPolicy.start_time <= now,
                or_(AccessPolicy.end_time == None, AccessPolicy.end_time >= now)
            ).filter(
                # Source IP match: NULL (all IPs) or specific user_source_ip_id
                or_(
                    AccessPolicy.source_ip_id == None,
                    AccessPolicy.source_ip_id == user_ip.id
                )
            ).filter(
                # Protocol match: NULL (all protocols) or specific
                or_(
                    AccessPolicy.protocol == None,
                    AccessPolicy.protocol == protocol
                )
            )
            
            # Check if user has direct policies for this server
            direct_user_policies = []
            for policy in user_policies_query:
                if policy.scope_type == 'group':
                    if policy.target_group_id in server_group_ids:
                        direct_user_policies.append(policy)
                elif policy.scope_type in ('server', 'service'):
                    if policy.target_server_id == server.id:
                        direct_user_policies.append(policy)
            
            # If user has direct policies, use ONLY those (ignore group inheritance)
            if direct_user_policies:
                matching_policies = direct_user_policies
                logger.debug(f"Using {len(direct_user_policies)} direct user policies (ignoring groups)")
                
                # For SSH, filter by login BEFORE proceeding
                # If direct policy exists but login not allowed - DENY (no fallback to groups)
                if protocol == 'ssh' and ssh_login:
                    valid_policies = []
                    for policy in matching_policies:
                        allowed_logins = db.query(PolicySSHLogin).filter(
                            PolicySSHLogin.policy_id == policy.id
                        ).all()
                        
                        # No restrictions = all logins allowed
                        if not allowed_logins:
                            valid_policies.append(policy)
                        else:
                            # Check if requested login is in allowed list
                            for login in allowed_logins:
                                if login.allowed_login == ssh_login:
                                    valid_policies.append(policy)
                                    break
                    
                    if not valid_policies:
                        logger.warning(
                            f"Access denied: Login '{ssh_login}' not allowed for {user.username} "
                            f"to {server.name} (user has direct policy, group inheritance blocked)"
                        )
                        return {
                            'has_access': False,
                            'user': user,
                            'user_ip': user_ip,
                            'server': server,
                            'policies': matching_policies,
                            'reason': f'SSH login "{ssh_login}" not allowed by direct user policy'
                        }
                    
                    matching_policies = valid_policies
            else:
                # PRIORITY 2: No direct user policies, check group policies
                user_group_ids = get_all_user_groups(user.id, db)
                
                if not user_group_ids:
                    logger.warning(
                        f"Access denied: No direct policies and no groups for {user.username}"
                    )
                    return {
                        'has_access': False,
                        'user': user,
                        'user_ip': user_ip,
                        'server': server,
                        'policies': [],
                        'reason': 'No matching policy (user or group)'
                    }
                
                group_policies_query = db.query(AccessPolicy).filter(
                    AccessPolicy.user_group_id.in_(user_group_ids),
                    AccessPolicy.is_active == True,
                    AccessPolicy.start_time <= now,
                    or_(AccessPolicy.end_time == None, AccessPolicy.end_time >= now)
                ).filter(
                    # Protocol match: NULL (all protocols) or specific
                    or_(
                        AccessPolicy.protocol == None,
                        AccessPolicy.protocol == protocol
                    )
                )
                
                matching_policies = []
                for policy in group_policies_query:
                    if policy.scope_type == 'group':
                        if policy.target_group_id in server_group_ids:
                            matching_policies.append(policy)
                    elif policy.scope_type in ('server', 'service'):
                        if policy.target_server_id == server.id:
                            matching_policies.append(policy)
                
                logger.debug(f"Using {len(matching_policies)} group policies (no direct user policies)")
            
            if not matching_policies:
                logger.warning(
                    f"Access denied: No matching policy for {user.username} "
                    f"from {source_ip} to {server.name} ({protocol})"
                )
                return {
                    'has_access': False,
                    'user': user,
                    'user_ip': user_ip,
                    'server': server,
                    'policies': [],
                    'reason': f'No matching access policy'
                }
            
            # Step 4: For SSH with group policies, check login restrictions
            # (Direct user policies already filtered ssh_login above)
            if protocol == 'ssh' and ssh_login and not direct_user_policies:
                valid_policies = []
                for policy in matching_policies:
                    allowed_logins = db.query(PolicySSHLogin).filter(
                        PolicySSHLogin.policy_id == policy.id
                    ).all()
                    
                    # No restrictions = all logins allowed
                    if not allowed_logins:
                        valid_policies.append(policy)
                    else:
                        # Check if requested login is in allowed list
                        for login in allowed_logins:
                            if login.allowed_login == ssh_login:
                                valid_policies.append(policy)
                                break
                
                if not valid_policies:
                    logger.warning(
                        f"Access denied: Login '{ssh_login}' not allowed for {user.username} "
                        f"to {server.name} (group policies)"
                    )
                    return {
                        'has_access': False,
                        'user': user,
                        'user_ip': user_ip,
                        'server': server,
                        'policies': matching_policies,
                        'reason': f'SSH login "{ssh_login}" not allowed by group policy'
                    }
                
                matching_policies = valid_policies
            
            # Success!
            logger.info(
                f"Access granted: {user.username} from {source_ip} "
                f"to {server.name} ({protocol}" +
                (f", login={ssh_login}" if ssh_login else "") + 
                f") - {len(matching_policies)} matching policies"
            )
            
            return {
                'has_access': True,
                'user': user,
                'user_ip': user_ip,
                'server': server,
                'policies': matching_policies,
                'reason': 'Access granted'
            }
            
        except Exception as e:
            logger.error(f"Error checking access: {e}", exc_info=True)
            return {
                'has_access': False,
                'user': None,
                'user_ip': None,
                'server': None,
                'policies': [],
                'reason': f'Internal error: {str(e)}'
            }
    
    def check_access_legacy_fallback(
        self,
        db: Session,
        source_ip: str,
        username: Optional[str] = None
    ) -> dict:
        """
        Legacy access check using old access_grants table.
        Fallback for backward compatibility.
        """
        try:
            # Find user by source_ip or username+source_ip
            if username is None:
                # RDP mode: identify user by source_ip only
                user = db.query(User).filter(
                    User.source_ip == source_ip,
                    User.is_active == True
                ).first()
                
                if not user:
                    return {
                        'has_access': False,
                        'reason': f"No user found for source IP {source_ip}",
                        'user': None,
                        'server': None
                    }
            else:
                # SSH mode: find by username and verify source_ip
                user = db.query(User).filter(
                    User.username == username,
                    User.is_active == True
                ).first()
                
                if not user:
                    return {
                        'has_access': False,
                        'reason': f"User {username} not found or inactive",
                        'user': None,
                        'server': None
                    }
                
                # If user has source_ip set, verify it matches
                if user.source_ip and user.source_ip != source_ip:
                    logger.warning(f"Source IP mismatch for {username}: expected {user.source_ip}, got {source_ip}")
                    return {
                        'has_access': False,
                        'reason': f"Source IP {source_ip} not authorized for user {username}",
                        'user': None,
                        'server': None
                    }
            
            # Find active access grant for this user
            now = datetime.utcnow()
            grant = db.query(AccessGrant).filter(
                and_(
                    AccessGrant.user_id == user.id,
                    AccessGrant.is_active == True,
                    AccessGrant.start_time <= now,
                    AccessGrant.end_time >= now
                )
            ).first()
            
            if not grant:
                return {
                    'has_access': False,
                    'reason': f"No active access grant",
                    'user': user,
                    'server': None
                }
            
            # Get server from grant
            server = db.query(Server).filter(
                Server.id == grant.server_id,
                Server.is_active == True
            ).first()
            
            if not server:
                return {
                    'has_access': False,
                    'reason': f"Server not found or inactive",
                    'user': user,
                    'server': None
                }
            
            return {
                'has_access': True,
                'user': user,
                'server': server,
                'grant': grant,
                'reason': 'Access granted (legacy)'
            }
            
        except Exception as e:
            logger.error(f"Error in legacy access check: {e}", exc_info=True)
            return {
                'has_access': False,
                'user': None,
                'server': None,
                'reason': f'Internal error: {str(e)}'
            }
    
    def audit_access_attempt(
        self,
        db: Session,
        user_id: Optional[int],
        action: str,
        source_ip: str,
        destination: str,
        protocol: str,
        success: bool,
        details: Optional[str] = None
    ):
        """Log access attempt to audit log."""
        try:
            log = AuditLog(
                user_id=user_id,
                action=action,
                resource_type='access_attempt',
                source_ip=source_ip,
                success=success,
                details=f"Protocol: {protocol}, Destination: {destination}. {details or ''}"
            )
            db.add(log)
            db.commit()
        except Exception as e:
            logger.error(f"Error logging audit: {e}", exc_info=True)
            db.rollback()

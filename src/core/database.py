"""Database configuration and models."""
from sqlalchemy import create_engine, Column, Integer, String, DateTime, Boolean, ForeignKey, Text, CheckConstraint, or_, BigInteger
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime
import os
from dotenv import load_dotenv
from flask_login import UserMixin

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class User(UserMixin, Base):
    """User model - synchronized with FreeIPA."""
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(255), unique=True, nullable=False, index=True)
    email = Column(String(255))
    full_name = Column(String(255))
    source_ip = Column(String(45), index=True)  # DEPRECATED: Use user_source_ips table instead
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    access_grants = relationship("AccessGrant", back_populates="user")
    source_ips = relationship("UserSourceIP", back_populates="user", cascade="all, delete-orphan")
    access_policies = relationship("AccessPolicy", back_populates="user", cascade="all, delete-orphan")
    sessions = relationship("SessionRecording", back_populates="user")
    audit_logs = relationship("AuditLog", back_populates="user")


class Server(Base):
    """Target server model."""
    __tablename__ = "servers"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    ip_address = Column(String(45), nullable=False, index=True)  # IPv4/IPv6
    description = Column(Text)
    os_type = Column(String(50))  # linux, windows
    ssh_port = Column(Integer, default=22)
    rdp_port = Column(Integer, default=3389)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    access_grants = relationship("AccessGrant", back_populates="server")
    ip_allocations = relationship("IPAllocation", back_populates="server")
    group_memberships = relationship("ServerGroupMember", back_populates="server", cascade="all, delete-orphan")
    access_policies = relationship("AccessPolicy", back_populates="target_server")


class AccessGrant(Base):
    """User access grant with temporal permissions."""
    __tablename__ = "access_grants"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    server_id = Column(Integer, ForeignKey("servers.id"), nullable=False, index=True)
    protocol = Column(String(10), nullable=False)  # ssh, rdp
    start_time = Column(DateTime, nullable=False, default=datetime.utcnow)
    end_time = Column(DateTime, nullable=False)  # Temporal access
    is_active = Column(Boolean, default=True)
    granted_by = Column(String(255))
    reason = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    user = relationship("User", back_populates="access_grants")
    server = relationship("Server", back_populates="access_grants")


class IPAllocation(Base):
    """IP pool allocation tracking - supports both permanent server assignments and temporary user sessions."""
    __tablename__ = "ip_allocations"
    
    id = Column(Integer, primary_key=True, index=True)
    allocated_ip = Column(String(45), nullable=False, unique=True, index=True)
    server_id = Column(Integer, ForeignKey("servers.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)  # NULL for permanent server assignments
    source_ip = Column(String(45), nullable=True)  # NULL for permanent assignments, filled for session-based
    allocated_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=True)  # NULL for permanent assignments
    is_active = Column(Boolean, default=True)
    session_id = Column(String(255), unique=True, nullable=True)  # NULL for permanent assignments
    
    # Relationships
    server = relationship("Server", back_populates="ip_allocations")


class SessionRecording(Base):
    """Session recording metadata."""
    __tablename__ = "session_recordings"
    
    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String(255), unique=True, nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    server_id = Column(Integer, ForeignKey("servers.id"), nullable=False)
    protocol = Column(String(10), nullable=False)  # ssh, rdp
    source_ip = Column(String(45), nullable=False)
    allocated_ip = Column(String(45), nullable=False)
    recording_path = Column(Text, nullable=False)
    start_time = Column(DateTime, nullable=False, default=datetime.utcnow)
    end_time = Column(DateTime)
    duration_seconds = Column(Integer)
    file_size_bytes = Column(Integer)
    
    # Relationships
    user = relationship("User", back_populates="sessions")


class AuditLog(Base):
    """Audit log for all actions."""
    __tablename__ = "audit_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True)
    action = Column(String(100), nullable=False, index=True)
    resource_type = Column(String(50))  # user, server, access_grant, etc.
    resource_id = Column(Integer)
    source_ip = Column(String(45))
    success = Column(Boolean, nullable=False)
    details = Column(Text)
    timestamp = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
    
    # Relationships
    user = relationship("User", back_populates="audit_logs")


class UserSourceIP(Base):
    """Multiple source IPs per user - for flexible access control."""
    __tablename__ = "user_source_ips"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    source_ip = Column(String(45), nullable=False, index=True)
    label = Column(String(255))  # e.g., "Home", "Office", "VPN"
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    user = relationship("User", back_populates="source_ips")
    access_policies = relationship("AccessPolicy", back_populates="source_ip_ref")
    
    __table_args__ = (
        CheckConstraint("user_id IS NOT NULL", name="check_user_source_ip_user_id"),
    )


class ServerGroup(Base):
    """Server groups/tags for flexible access management."""
    __tablename__ = "server_groups"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), unique=True, nullable=False, index=True)
    description = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    members = relationship("ServerGroupMember", back_populates="group", cascade="all, delete-orphan")
    access_policies = relationship("AccessPolicy", back_populates="target_group")


class ServerGroupMember(Base):
    """N:M relationship: servers can belong to multiple groups."""
    __tablename__ = "server_group_members"
    
    id = Column(Integer, primary_key=True, index=True)
    server_id = Column(Integer, ForeignKey("servers.id"), nullable=False, index=True)
    group_id = Column(Integer, ForeignKey("server_groups.id"), nullable=False, index=True)
    added_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    server = relationship("Server", back_populates="group_memberships")
    group = relationship("ServerGroup", back_populates="members")
    
    __table_args__ = (
        CheckConstraint("server_id IS NOT NULL AND group_id IS NOT NULL", name="check_group_member_ids"),
    )


class AccessPolicy(Base):
    """Flexible access policy with granular control (group/server/service level)."""
    __tablename__ = "access_policies"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    
    # Source IP restriction (NULL = all user's IPs allowed)
    source_ip_id = Column(Integer, ForeignKey("user_source_ips.id"), index=True)
    
    # Scope: 'group' (all servers in group), 'server' (specific server), 'service' (server+protocol)
    scope_type = Column(String(20), nullable=False, index=True)
    
    # Target references (based on scope_type)
    target_group_id = Column(Integer, ForeignKey("server_groups.id"), index=True)
    target_server_id = Column(Integer, ForeignKey("servers.id"), index=True)
    
    # Protocol filter (NULL = all protocols, 'ssh', 'rdp')
    protocol = Column(String(10))
    
    # Temporal access
    start_time = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
    end_time = Column(DateTime, nullable=True, index=True)  # NULL = permanent access
    
    is_active = Column(Boolean, default=True, index=True)
    granted_by = Column(String(255))
    reason = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    user = relationship("User", back_populates="access_policies")
    source_ip_ref = relationship("UserSourceIP", back_populates="access_policies")
    target_group = relationship("ServerGroup", back_populates="access_policies")
    target_server = relationship("Server", back_populates="access_policies")
    ssh_logins = relationship("PolicySSHLogin", back_populates="policy", cascade="all, delete-orphan")
    
    __table_args__ = (
        CheckConstraint(
            "scope_type IN ('group', 'server', 'service')",
            name="check_scope_type_valid"
        ),
        CheckConstraint(
            "protocol IS NULL OR protocol IN ('ssh', 'rdp')",
            name="check_protocol_valid"
        ),
        CheckConstraint(
            "(scope_type = 'group' AND target_group_id IS NOT NULL AND target_server_id IS NULL) OR "
            "(scope_type IN ('server', 'service') AND target_server_id IS NOT NULL AND target_group_id IS NULL)",
            name="check_scope_targets"
        ),
    )


class PolicySSHLogin(Base):
    """SSH login restrictions for access policies. Empty = all logins allowed."""
    __tablename__ = "policy_ssh_logins"
    
    id = Column(Integer, primary_key=True, index=True)
    policy_id = Column(Integer, ForeignKey("access_policies.id", ondelete="CASCADE"), nullable=False, index=True)
    allowed_login = Column(String(255), nullable=False)
    
    # Relationships
    policy = relationship("AccessPolicy", back_populates="ssh_logins")
    
    __table_args__ = (
        CheckConstraint("policy_id IS NOT NULL", name="check_ssh_login_policy_id"),
    )


class Session(Base):
    """Active and historical connection sessions (SSH/RDP)."""
    __tablename__ = "sessions"
    
    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String(255), unique=True, nullable=False, index=True)  # Unique session identifier
    
    # Session details
    user_id = Column(Integer, ForeignKey("users.id"), index=True)
    server_id = Column(Integer, ForeignKey("servers.id"), index=True)
    protocol = Column(String(10), nullable=False, index=True)  # ssh, rdp
    
    # Connection info
    source_ip = Column(String(45), nullable=False)
    proxy_ip = Column(String(45))  # IP from pool used for this session
    backend_ip = Column(String(45), nullable=False)
    backend_port = Column(Integer, nullable=False)
    ssh_username = Column(String(255))  # SSH login used
    subsystem_name = Column(String(50))  # sftp, scp, etc.
    ssh_agent_used = Column(Boolean, default=False)  # True if SSH agent was used
    
    # Timing
    started_at = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
    ended_at = Column(DateTime, index=True)  # NULL = active session
    duration_seconds = Column(Integer)  # Calculated on end
    
    # Recording
    recording_path = Column(String(512))  # Path to session recording file
    recording_size = Column(BigInteger)  # Size in bytes
    
    # Status
    is_active = Column(Boolean, default=True, index=True)
    termination_reason = Column(String(255))  # normal, timeout, error, killed
    
    # Audit trail
    policy_id = Column(Integer, ForeignKey("access_policies.id"))  # Which policy granted access
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    user = relationship("User")
    server = relationship("Server")
    policy = relationship("AccessPolicy")
    
    __table_args__ = (
        CheckConstraint(
            "protocol IN ('ssh', 'rdp')",
            name="check_session_protocol_valid"
        ),
    )


def init_db():
    """Initialize database tables."""
    Base.metadata.create_all(bind=engine)
    print("Database tables created successfully!")


def get_db():
    """Get database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


if __name__ == "__main__":
    init_db()

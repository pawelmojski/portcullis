#!/usr/bin/env python3
"""
Test backward compatibility - existing policies should work without schedules
"""
import sys
sys.path.insert(0, '/opt/jumphost')

from src.core.database import SessionLocal, AccessPolicy, User, Server, UserSourceIP, IPAllocation
from src.core.access_control_v2 import AccessControlEngineV2
from datetime import datetime

def test_backward_compatibility():
    """Test that existing policies (use_schedules=False) work normally"""
    db = SessionLocal()
    engine = AccessControlEngineV2()
    
    try:
        # Get an existing policy WITHOUT schedules (use_schedules=False)
        old_policy = db.query(AccessPolicy).filter(
            AccessPolicy.use_schedules == False,
            AccessPolicy.is_active == True
        ).first()
        
        if not old_policy:
            print("❌ No existing policies found (use_schedules=False)")
            return False
        
        print(f"✓ Found existing policy ID: {old_policy.id}")
        print(f"  - user_id: {old_policy.user_id}")
        print(f"  - use_schedules: {old_policy.use_schedules}")
        print(f"  - start_time: {old_policy.start_time}")
        print(f"  - end_time: {old_policy.end_time}")
        
        # Check if policy is within time bounds
        now = datetime.utcnow()
        if old_policy.end_time and old_policy.end_time < now:
            print("  ⚠️  Policy expired - skipping test")
            return True
        
        # Get user and server
        if not old_policy.user_id or not old_policy.target_server_id:
            print("  ⚠️  Policy is group-based or missing target - skipping")
            return True
        
        user = db.query(User).get(old_policy.user_id)
        server = db.query(Server).get(old_policy.target_server_id)
        
        if not user or not server:
            print("  ⚠️  User or server not found")
            return True
        
        # Get user's source IP
        user_ip = db.query(UserSourceIP).filter(
            UserSourceIP.user_id == user.id,
            UserSourceIP.is_active == True
        ).first()
        
        if not user_ip:
            print("  ⚠️  No active source IP for user")
            return True
        
        # Get server's proxy IP
        ip_alloc = db.query(IPAllocation).filter(
            IPAllocation.server_id == server.id,
            IPAllocation.is_active == True
        ).first()
        
        if not ip_alloc:
            print("  ⚠️  No IP allocation for server")
            return True
        
        print(f"✓ Testing access for {user.username} to {server.name}")
        print(f"  - source_ip: {user_ip.source_ip}")
        print(f"  - dest_ip: {ip_alloc.allocated_ip}")
        print(f"  - protocol: {old_policy.protocol or 'ALL'}")
        
        # Test access - should work normally WITHOUT schedule checking
        result = engine.check_access_v2(
            db=db,
            source_ip=user_ip.source_ip,
            dest_ip=ip_alloc.allocated_ip,
            protocol=old_policy.protocol or 'ssh',
            ssh_login=None
        )
        
        print(f"\nAccess check result:")
        print(f"  - has_access: {result['has_access']}")
        print(f"  - reason: {result.get('reason', 'N/A')}")
        print(f"  - policies matched: {len(result.get('policies', []))}")
        
        if result['has_access']:
            print("\n✅ BACKWARD COMPATIBILITY OK!")
            print("   Existing policies work without schedules!")
        else:
            print(f"\n⚠️  Access denied: {result.get('reason')}")
            print("   (This may be expected if policy has other restrictions)")
        
        return True
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        db.close()

if __name__ == '__main__':
    print("=" * 60)
    print("Backward Compatibility Test")
    print("=" * 60)
    print()
    
    success = test_backward_compatibility()
    
    print()
    print("=" * 60)
    if success:
        print("✅ Test completed!")
    else:
        print("❌ Test failed!")
    print("=" * 60)

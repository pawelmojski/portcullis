#!/usr/bin/env python3
"""
Test policy priority - multiple policies with and without schedules
"""
import sys
sys.path.insert(0, '/opt/jumphost')

from src.core.database import SessionLocal, AccessPolicy, User, Server, PolicySchedule, UserSourceIP, IPAllocation
from src.core.access_control_v2 import AccessControlEngineV2
from datetime import datetime, time
import pytz

def test_policy_priority():
    """Test what happens when user has multiple policies - with and without schedules"""
    db = SessionLocal()
    engine = AccessControlEngineV2()
    
    try:
        # Get first user and server
        user = db.query(User).filter(User.is_active == True).first()
        server = db.query(Server).filter(Server.is_active == True).first()
        
        if not user or not server:
            print("❌ No active user or server found")
            return False
        
        print(f"✓ Testing with user: {user.username}, server: {server.name}\n")
        
        # Create Policy A: 24/7 access (no schedules)
        policy_a = AccessPolicy(
            user_id=user.id,
            target_server_id=server.id,
            scope_type='server',
            protocol='ssh',
            is_active=True,
            use_schedules=False,  # NO schedule restrictions
            start_time=datetime(2026, 1, 1, 0, 0),
            end_time=None  # Permanent
        )
        db.add(policy_a)
        db.flush()
        print(f"✓ Created Policy A (ID: {policy_a.id})")
        print(f"  - use_schedules: False (24/7 access)")
        
        # Create Policy B: With schedule Mon-Fri 8-16
        policy_b = AccessPolicy(
            user_id=user.id,
            target_server_id=server.id,
            scope_type='server',
            protocol='ssh',
            is_active=True,
            use_schedules=True,  # Schedule enabled
            start_time=datetime(2026, 1, 1, 0, 0),
            end_time=None
        )
        db.add(policy_b)
        db.flush()
        
        schedule = PolicySchedule(
            policy_id=policy_b.id,
            name="Business Hours Only",
            weekdays=[0, 1, 2, 3, 4],  # Mon-Fri
            time_start=time(8, 0),
            time_end=time(16, 0),
            months=None,
            days_of_month=None,
            timezone='Europe/Warsaw',
            is_active=True
        )
        db.add(schedule)
        db.commit()
        
        print(f"✓ Created Policy B (ID: {policy_b.id})")
        print(f"  - use_schedules: True (Mon-Fri 8-16 only)\n")
        
        # Get user's source IP and server's proxy IP
        user_ip = db.query(UserSourceIP).filter(UserSourceIP.user_id == user.id).first()
        if not user_ip:
            user_ip = UserSourceIP(
                user_id=user.id,
                source_ip='192.168.1.100',
                label='Test IP',
                is_active=True
            )
            db.add(user_ip)
            db.commit()
        
        ip_alloc = db.query(IPAllocation).filter(
            IPAllocation.server_id == server.id,
            IPAllocation.is_active == True
        ).first()
        
        if not ip_alloc:
            print("❌ No IP allocation for server")
            return False
        
        warsaw_tz = pytz.timezone('Europe/Warsaw')
        
        print("=" * 60)
        print("TEST SCENARIO:")
        print("User has TWO policies:")
        print("  A) 24/7 access (no schedule)")
        print("  B) Mon-Fri 8-16 only (with schedule)")
        print("\nQuestion: What happens on SATURDAY at 10:00?")
        print("=" * 60)
        print()
        
        # Test: Saturday 10:00 (WEEKEND - Policy B should block, but Policy A should allow)
        test_time = warsaw_tz.localize(datetime(2026, 1, 10, 10, 0))  # Saturday
        test_time_utc = test_time.astimezone(pytz.UTC).replace(tzinfo=None)
        
        result = engine.check_access_v2(
            db=db,
            source_ip=user_ip.source_ip,
            dest_ip=ip_alloc.allocated_ip,
            protocol='ssh',
            ssh_login='root',
            check_time=test_time_utc
        )
        
        print(f"Access check at Saturday 10:00 Warsaw:")
        print(f"  - Policy A evaluation: ✅ PASS (no schedule, always active)")
        print(f"  - Policy B evaluation: ❌ FAIL (weekend, outside Mon-Fri)")
        print()
        print(f"RESULT:")
        print(f"  - has_access: {result['has_access']}")
        print(f"  - reason: {result.get('reason', 'Access granted')}")
        print(f"  - matching policies: {len(result.get('policies', []))}")
        print()
        
        if result['has_access']:
            print("✅ VERDICT: Policy A (24/7) wins!")
            print("   Access GRANTED even though Policy B would block.")
            print("   Logic: OR operation - if ANY policy allows, access is granted.")
        else:
            print("❌ UNEXPECTED: Access denied!")
            print(f"   Reason: {result.get('reason')}")
        
        # Cleanup
        db.delete(schedule)
        db.delete(policy_b)
        db.delete(policy_a)
        db.commit()
        print("\n✓ Cleanup complete")
        
        return result['has_access']  # Should be True
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        db.rollback()
        return False
    finally:
        db.close()

if __name__ == '__main__':
    print("=" * 60)
    print("Policy Priority Test")
    print("=" * 60)
    print()
    
    success = test_policy_priority()
    
    print()
    print("=" * 60)
    if success:
        print("✅ Test passed! Policy without schedule takes priority.")
    else:
        print("❌ Test failed!")
    print("=" * 60)

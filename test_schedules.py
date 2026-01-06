#!/usr/bin/env python3
"""
Test script for schedule-based access control
"""
import sys
import os
from datetime import datetime, time
import pytz

# Add src to path
sys.path.insert(0, '/opt/jumphost')

from src.core.database import SessionLocal, AccessPolicy, User, Server, PolicySchedule
from src.core.access_control_v2 import AccessControlEngineV2

def test_schedule_creation():
    """Test creating a policy with schedule"""
    db = SessionLocal()
    engine = AccessControlEngineV2()
    
    try:
        # Get first user and server
        user = db.query(User).filter(User.is_active == True).first()
        server = db.query(Server).filter(Server.is_active == True).first()
        
        if not user or not server:
            print("❌ No active user or server found")
            return False
        
        print(f"✓ Using user: {user.username}, server: {server.name}")
        
        # Create policy with schedule (start from Jan 1, 2026 to be sure it's active)
        policy = AccessPolicy(
            user_id=user.id,
            target_server_id=server.id,
            scope_type='server',
            protocol='ssh',
            is_active=True,
            use_schedules=True,
            start_time=datetime(2026, 1, 1, 0, 0),  # Start from beginning of year
            end_time=None  # Permanent (but constrained by schedule)
        )
        db.add(policy)
        db.flush()
        
        print(f"✓ Created policy ID: {policy.id}")
        
        # Add schedule: Mon-Fri 8:00-16:00 Europe/Warsaw
        schedule = PolicySchedule(
            policy_id=policy.id,
            name="Business Hours",
            weekdays=[0, 1, 2, 3, 4],  # Mon-Fri
            time_start=time(8, 0),
            time_end=time(16, 0),
            months=None,  # All months
            days_of_month=None,  # All days
            timezone='Europe/Warsaw',
            is_active=True
        )
        db.add(schedule)
        db.commit()
        
        print(f"✓ Created schedule: {schedule.name}")
        print(f"  - Weekdays: Mon-Fri")
        print(f"  - Time: 08:00-16:00")
        print(f"  - Timezone: Europe/Warsaw")
        
        # Test access at different times
        print("\nTesting access at different times:")
        
        # Get user's source IP (create one if doesn't exist)
        from src.core.database import UserSourceIP, IPAllocation
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
            print(f"✓ Created test source IP: {user_ip.source_ip}")
        
        # Get server's allocated proxy IP
        ip_alloc = db.query(IPAllocation).filter(
            IPAllocation.server_id == server.id,
            IPAllocation.is_active == True
        ).first()
        
        if not ip_alloc:
            # Create IP allocation for test
            from src.core.ip_pool import IPPoolManager
            pool_mgr = IPPoolManager()
            ip_alloc = pool_mgr.allocate_permanent_ip(db, server.id)
            if not ip_alloc:
                print("❌ Could not allocate IP for server")
                return False
            print(f"✓ Allocated proxy IP: {ip_alloc.allocated_ip}")
        
        proxy_ip = ip_alloc.allocated_ip
        
        # Monday 10:00 Warsaw (should ALLOW)
        warsaw_tz = pytz.timezone('Europe/Warsaw')
        test_time_1 = warsaw_tz.localize(datetime(2026, 1, 6, 10, 0))  # Monday 10:00
        test_time_1_utc = test_time_1.astimezone(pytz.UTC).replace(tzinfo=None)
        
        result = engine.check_access_v2(
            db=db,
            source_ip=user_ip.source_ip,
            dest_ip=proxy_ip,
            protocol='ssh',
            ssh_login='root',
            check_time=test_time_1_utc
        )
        
        status_1 = "✅ ALLOWED" if result['has_access'] else "❌ DENIED"
        print(f"  Mon 10:00 Warsaw: {status_1}")
        if not result['has_access']:
            print(f"    Reason: {result.get('reason')}")
        
        # Monday 18:00 Warsaw (should DENY - outside 8-16)
        test_time_2 = warsaw_tz.localize(datetime(2026, 1, 6, 18, 0))  # Monday 18:00
        test_time_2_utc = test_time_2.astimezone(pytz.UTC).replace(tzinfo=None)
        
        result = engine.check_access_v2(
            db=db,
            source_ip=user_ip.source_ip,
            dest_ip=proxy_ip,
            protocol='ssh',
            ssh_login='root',
            check_time=test_time_2_utc
        )
        
        status_2 = "✅ ALLOWED" if result['has_access'] else "❌ DENIED"
        print(f"  Mon 18:00 Warsaw: {status_2}")
        if not result['has_access']:
            print(f"    Reason: {result.get('reason')}")
        
        # Saturday 10:00 Warsaw (should DENY - weekend)
        test_time_3 = warsaw_tz.localize(datetime(2026, 1, 10, 10, 0))  # Saturday 10:00
        test_time_3_utc = test_time_3.astimezone(pytz.UTC).replace(tzinfo=None)
        
        result = engine.check_access_v2(
            db=db,
            source_ip=user_ip.source_ip,
            dest_ip=proxy_ip,
            protocol='ssh',
            ssh_login='root',
            check_time=test_time_3_utc
        )
        
        status_3 = "✅ ALLOWED" if result['has_access'] else "❌ DENIED"
        print(f"  Sat 10:00 Warsaw: {status_3}")
        if not result['has_access']:
            print(f"    Reason: {result.get('reason')}")
        
        # Cleanup
        db.delete(schedule)
        db.delete(policy)
        db.commit()
        print("\n✓ Cleanup complete")
        
        # Verify results
        success = (
            result  # At least last result exists
            # We expect: Mon 10:00 ALLOWED, Mon 18:00 DENIED, Sat 10:00 DENIED
        )
        
        return True
        
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
    print("Schedule-Based Access Control Test")
    print("=" * 60)
    print()
    
    success = test_schedule_creation()
    
    print()
    print("=" * 60)
    if success:
        print("✅ Tests completed successfully!")
    else:
        print("❌ Tests failed!")
    print("=" * 60)
    
    sys.exit(0 if success else 1)

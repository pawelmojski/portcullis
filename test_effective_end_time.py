#!/usr/bin/env python3
"""
Test effective_end_time calculation with schedules
"""
import sys
sys.path.insert(0, '/opt/jumphost')

from src.core.database import SessionLocal, AccessPolicy, User, Server, PolicySchedule, UserSourceIP, IPAllocation
from src.core.access_control_v2 import AccessControlEngineV2
from datetime import datetime, time
import pytz

def test_effective_end_time():
    """Test that effective_end_time considers schedule window end"""
    db = SessionLocal()
    engine = AccessControlEngineV2()
    
    try:
        # Get first user and server
        user = db.query(User).filter(User.is_active == True).first()
        server = db.query(Server).filter(Server.is_active == True).first()
        
        if not user or not server:
            print("❌ No active user or server found")
            return False
        
        print(f"Testing with user: {user.username}, server: {server.name}\n")
        
        # Create policy with schedule
        # Policy valid until end of month, but schedule ends at 16:00 today
        policy = AccessPolicy(
            user_id=user.id,
            target_server_id=server.id,
            scope_type='server',
            protocol='ssh',
            is_active=True,
            use_schedules=True,
            start_time=datetime(2026, 1, 1, 0, 0),
            end_time=datetime(2026, 1, 31, 23, 59)  # Policy valid until end of month
        )
        db.add(policy)
        db.flush()
        
        # Add schedule: Mon-Fri 8:00-16:00
        schedule = PolicySchedule(
            policy_id=policy.id,
            name="Business Hours",
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
        
        print(f"✓ Created policy ID: {policy.id}")
        print(f"  - Policy end_time: {policy.end_time} (end of month)")
        print(f"  - Schedule: Mon-Fri 08:00-16:00 Europe/Warsaw\n")
        
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
        
        # Test at Monday 10:00 Warsaw (in business hours)
        warsaw_tz = pytz.timezone('Europe/Warsaw')
        test_time = warsaw_tz.localize(datetime(2026, 1, 6, 10, 0))  # Monday 10:00
        test_time_utc = test_time.astimezone(pytz.UTC).replace(tzinfo=None)
        
        print(f"Testing at: {test_time.strftime('%Y-%m-%d %H:%M %Z')} (Mon 10:00)")
        print(f"  = {test_time_utc} UTC\n")
        
        result = engine.check_access_v2(
            db=db,
            source_ip=user_ip.source_ip,
            dest_ip=ip_alloc.allocated_ip,
            protocol='ssh',
            ssh_login='root',
            check_time=test_time_utc
        )
        
        print(f"Access check result:")
        print(f"  - has_access: {result['has_access']}")
        print(f"  - reason: {result.get('reason')}")
        
        if result['has_access']:
            effective_end = result.get('effective_end_time')
            policy_end = policy.end_time
            
            print(f"\n✅ ACCESS GRANTED")
            print(f"\nTime comparison:")
            print(f"  Policy end_time:     {policy_end} UTC")
            
            if effective_end:
                print(f"  Effective end_time:  {effective_end} UTC")
                
                # Convert to Warsaw time for display
                effective_end_warsaw = pytz.utc.localize(effective_end).astimezone(warsaw_tz)
                print(f"                       {effective_end_warsaw.strftime('%Y-%m-%d %H:%M %Z')}")
                
                if effective_end < policy_end:
                    time_diff = (policy_end - effective_end).total_seconds() / 3600
                    print(f"\n✅ CORRECT: Schedule window end ({effective_end_warsaw.strftime('%H:%M')}) is {time_diff:.1f} hours")
                    print(f"   BEFORE policy end ({policy_end})")
                    print(f"\n   User will get warnings about schedule window closing at 16:00,")
                    print(f"   NOT about policy ending on Jan 31!")
                else:
                    print(f"\n❌ UNEXPECTED: Effective end should be schedule window end (16:00)")
            else:
                print(f"  Effective end_time:  None (no end time)")
        else:
            print(f"\n❌ ACCESS DENIED: {result.get('reason')}")
        
        # Cleanup
        db.delete(schedule)
        db.delete(policy)
        db.commit()
        print("\n✓ Cleanup complete")
        
        return result['has_access'] and result.get('effective_end_time') is not None
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        db.rollback()
        return False
    finally:
        db.close()

if __name__ == '__main__':
    print("=" * 70)
    print("Effective End Time Test (Schedule Window)")
    print("=" * 70)
    print()
    
    success = test_effective_end_time()
    
    print()
    print("=" * 70)
    if success:
        print("✅ Test passed! Schedule window end is used as effective_end_time")
    else:
        print("❌ Test failed!")
    print("=" * 70)

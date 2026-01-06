#!/usr/bin/env python3
"""
Test effective_end_time when policy ends BEFORE schedule window
"""
import sys
sys.path.insert(0, '/opt/jumphost')

from src.core.database import SessionLocal, AccessPolicy, User, Server, PolicySchedule, UserSourceIP, IPAllocation
from src.core.access_control_v2 import AccessControlEngineV2
from datetime import datetime, time
import pytz

def test_policy_ends_first():
    """Test that effective_end_time uses policy end when it's earlier than schedule"""
    db = SessionLocal()
    engine = AccessControlEngineV2()
    
    try:
        user = db.query(User).filter(User.is_active == True).first()
        server = db.query(Server).filter(Server.is_active == True).first()
        
        if not user or not server:
            print("❌ No active user or server found")
            return False
        
        print(f"Testing with user: {user.username}, server: {server.name}\n")
        
        # Policy ends at 14:00 today (earlier than schedule window end at 16:00)
        warsaw_tz = pytz.timezone('Europe/Warsaw')
        policy_end_local = warsaw_tz.localize(datetime(2026, 1, 6, 14, 0))  # 14:00 today
        policy_end_utc = policy_end_local.astimezone(pytz.utc).replace(tzinfo=None)
        
        policy = AccessPolicy(
            user_id=user.id,
            target_server_id=server.id,
            scope_type='server',
            protocol='ssh',
            is_active=True,
            use_schedules=True,
            start_time=datetime(2026, 1, 1, 0, 0),
            end_time=policy_end_utc  # Policy ends at 14:00 (before schedule 16:00)
        )
        db.add(policy)
        db.flush()
        
        # Schedule: Mon-Fri 8:00-16:00 (ends at 16:00)
        schedule = PolicySchedule(
            policy_id=policy.id,
            name="Business Hours",
            weekdays=[0, 1, 2, 3, 4],
            time_start=time(8, 0),
            time_end=time(16, 0),  # Schedule ends at 16:00
            months=None,
            days_of_month=None,
            timezone='Europe/Warsaw',
            is_active=True
        )
        db.add(schedule)
        db.commit()
        
        print(f"✓ Created policy ID: {policy.id}")
        print(f"  - Policy end_time: {policy_end_local.strftime('%Y-%m-%d %H:%M %Z')} (14:00)")
        print(f"  - Schedule end:    2026-01-06 16:00 CET (business hours)")
        print(f"  → Policy ends 2 hours BEFORE schedule window\n")
        
        # Get IPs
        user_ip = db.query(UserSourceIP).filter(UserSourceIP.user_id == user.id).first()
        if not user_ip:
            user_ip = UserSourceIP(user_id=user.id, source_ip='192.168.1.100', label='Test', is_active=True)
            db.add(user_ip)
            db.commit()
        
        ip_alloc = db.query(IPAllocation).filter(
            IPAllocation.server_id == server.id,
            IPAllocation.is_active == True
        ).first()
        
        if not ip_alloc:
            print("❌ No IP allocation")
            return False
        
        # Test at Monday 10:00 (both policy and schedule are active)
        test_time = warsaw_tz.localize(datetime(2026, 1, 6, 10, 0))
        test_time_utc = test_time.astimezone(pytz.UTC).replace(tzinfo=None)
        
        print(f"Testing at: {test_time.strftime('%Y-%m-%d %H:%M %Z')}\n")
        
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
        
        if result['has_access']:
            effective_end = result.get('effective_end_time')
            
            print(f"\n✅ ACCESS GRANTED")
            print(f"\nTime comparison:")
            print(f"  Policy end_time:     {policy_end_utc} UTC ({policy_end_local.strftime('%H:%M %Z')})")
            
            if effective_end:
                effective_end_warsaw = pytz.utc.localize(effective_end).astimezone(warsaw_tz)
                print(f"  Effective end_time:  {effective_end} UTC")
                print(f"                       {effective_end_warsaw.strftime('%Y-%m-%d %H:%M %Z')}")
                
                schedule_end_local = warsaw_tz.localize(datetime(2026, 1, 6, 16, 0))
                print(f"  Schedule window end: {schedule_end_local.strftime('%Y-%m-%d %H:%M %Z')}")
                
                if effective_end == policy_end_utc:
                    print(f"\n✅ CORRECT: effective_end_time = policy.end_time (14:00)")
                    print(f"   Policy ends BEFORE schedule window (14:00 < 16:00)")
                    print(f"\n   User will get warnings about policy ending at 14:00,")
                    print(f"   NOT about schedule window closing at 16:00!")
                    success = True
                elif effective_end < policy_end_utc:
                    print(f"\n✅ ALSO CORRECT: effective_end_time is even earlier")
                    success = True
                else:
                    print(f"\n❌ WRONG: effective_end_time should be policy end (14:00), not schedule end (16:00)")
                    success = False
            else:
                print(f"  Effective end_time:  None")
                success = False
        else:
            print(f"\n❌ ACCESS DENIED: {result.get('reason')}")
            success = False
        
        # Cleanup
        db.delete(schedule)
        db.delete(policy)
        db.commit()
        print("\n✓ Cleanup complete")
        
        return success
        
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
    print("Test: Policy Ends BEFORE Schedule Window")
    print("=" * 70)
    print()
    
    success = test_policy_ends_first()
    
    print()
    print("=" * 70)
    if success:
        print("✅ Test passed! Policy end_time is used when earlier than schedule")
    else:
        print("❌ Test failed!")
    print("=" * 70)

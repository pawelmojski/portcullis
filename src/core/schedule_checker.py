"""Schedule checker - validates if current time matches policy schedule rules"""
from datetime import datetime, time, timedelta
from typing import List, Optional
import pytz
import logging

logger = logging.getLogger(__name__)


def get_schedule_window_end(
    schedule_rule: dict,
    check_time: Optional[datetime] = None
) -> Optional[datetime]:
    """
    Get the end time of the current schedule window.
    
    Args:
        schedule_rule: Dict with schedule configuration
        check_time: Current time to check (default: now in UTC)
    
    Returns:
        datetime of when current window ends (in UTC), or None if not in window
    
    Example:
        If schedule is Mon-Fri 8-16 and current time is Mon 10:00 Warsaw,
        returns Mon 16:00 UTC (today at end of business hours)
    """
    if check_time is None:
        check_time = datetime.utcnow()
    
    # First check if we're currently in a valid window
    if not matches_schedule(schedule_rule, check_time):
        return None
    
    # Convert to policy timezone
    tz = pytz.timezone(schedule_rule.get('timezone', 'Europe/Warsaw'))
    if check_time.tzinfo is None:
        check_time = pytz.utc.localize(check_time)
    
    local_time = check_time.astimezone(tz)
    
    # Get time_end from schedule
    time_end = schedule_rule.get('time_end')
    if time_end is None:
        time_end = time(23, 59, 59)
    
    # Create datetime for end of current window (today at time_end in policy timezone)
    window_end_local = tz.localize(datetime(
        local_time.year,
        local_time.month,
        local_time.day,
        time_end.hour,
        time_end.minute,
        time_end.second
    ))
    
    # Convert back to UTC
    window_end_utc = window_end_local.astimezone(pytz.utc)
    
    # Remove timezone info to return naive datetime (for consistency with database)
    return window_end_utc.replace(tzinfo=None)


def get_earliest_schedule_end(
    schedules: List[dict],
    check_time: Optional[datetime] = None
) -> Optional[datetime]:
    """
    Get the earliest end time among all active schedule windows.
    
    Args:
        schedules: List of schedule rules
        check_time: Current time to check
    
    Returns:
        Earliest schedule window end time (UTC), or None if no active windows
    
    Example:
        If current time matches multiple schedules, returns the earliest end time.
        Used to determine when to warn user about session expiry.
    """
    if not schedules:
        return None
    
    end_times = []
    for schedule in schedules:
        if not schedule.get('is_active', True):
            continue
        
        window_end = get_schedule_window_end(schedule, check_time)
        if window_end:
            end_times.append(window_end)
    
    return min(end_times) if end_times else None


def matches_schedule(
    schedule_rule: dict,
    check_time: Optional[datetime] = None
) -> bool:
    """
    Check if given time matches schedule rule.
    
    Args:
        schedule_rule: Dict with keys: weekdays, time_start, time_end, months, 
                      days_of_month, timezone
        check_time: Datetime to check (default: now in UTC)
    
    Returns:
        True if time matches schedule, False otherwise
    
    Example schedule_rule:
        {
            'weekdays': [0, 1, 2, 3, 4],  # Mon-Fri
            'time_start': time(8, 0),      # 08:00
            'time_end': time(16, 0),       # 16:00
            'months': None,                # All months
            'days_of_month': None,         # All days
            'timezone': 'Europe/Warsaw'
        }
    """
    if check_time is None:
        check_time = datetime.utcnow()
    
    # Convert to policy timezone
    tz = pytz.timezone(schedule_rule.get('timezone', 'Europe/Warsaw'))
    if check_time.tzinfo is None:
        # Assume UTC if no timezone
        check_time = pytz.utc.localize(check_time)
    
    local_time = check_time.astimezone(tz)
    
    # Check weekday (0=Monday, 6=Sunday)
    weekdays = schedule_rule.get('weekdays')
    if weekdays is not None and len(weekdays) > 0:
        if local_time.weekday() not in weekdays:
            logger.debug(f"Schedule check failed: weekday {local_time.weekday()} not in {weekdays}")
            return False
    
    # Check time range
    time_start = schedule_rule.get('time_start')
    time_end = schedule_rule.get('time_end')
    
    if time_start is not None or time_end is not None:
        current_time = local_time.time()
        
        # Default to full day if not specified
        if time_start is None:
            time_start = time(0, 0)
        if time_end is None:
            time_end = time(23, 59, 59)
        
        # Handle time ranges that cross midnight
        if time_start <= time_end:
            # Normal range: 08:00 - 16:00
            if not (time_start <= current_time <= time_end):
                logger.debug(f"Schedule check failed: time {current_time} not in {time_start}-{time_end}")
                return False
        else:
            # Crosses midnight: 22:00 - 02:00
            if not (current_time >= time_start or current_time <= time_end):
                logger.debug(f"Schedule check failed: time {current_time} not in {time_start}-{time_end} (overnight)")
                return False
    
    # Check month (1-12)
    months = schedule_rule.get('months')
    if months is not None and len(months) > 0:
        if local_time.month not in months:
            logger.debug(f"Schedule check failed: month {local_time.month} not in {months}")
            return False
    
    # Check day of month (1-31)
    days_of_month = schedule_rule.get('days_of_month')
    if days_of_month is not None and len(days_of_month) > 0:
        if local_time.day not in days_of_month:
            logger.debug(f"Schedule check failed: day {local_time.day} not in {days_of_month}")
            return False
    
    logger.debug(f"Schedule check passed for {local_time}")
    return True


def check_policy_schedules(
    schedules: List[dict],
    check_time: Optional[datetime] = None
) -> tuple[bool, Optional[str]]:
    """
    Check if current time matches ANY of the policy schedules.
    
    Args:
        schedules: List of schedule rule dicts
        check_time: Datetime to check (default: now)
    
    Returns:
        (matches: bool, matched_name: str or None)
        - If any schedule matches: (True, schedule_name)
        - If no schedules match: (False, None)
        - If no schedules defined: (True, None) - allow access (schedule disabled)
    
    Example:
        schedules = [
            {
                'name': 'Business hours',
                'weekdays': [0,1,2,3,4],
                'time_start': time(8, 0),
                'time_end': time(16, 0),
                'timezone': 'Europe/Warsaw'
            },
            {
                'name': 'Weekend maintenance',
                'weekdays': [5, 6],
                'time_start': time(2, 0),
                'time_end': time(6, 0),
                'timezone': 'Europe/Warsaw'
            }
        ]
        
        # On Monday at 10:00 → (True, 'Business hours')
        # On Saturday at 04:00 → (True, 'Weekend maintenance')
        # On Monday at 18:00 → (False, None)
    """
    if not schedules or len(schedules) == 0:
        # No schedules = always allow (schedule-based access disabled)
        return (True, None)
    
    # Check each schedule - if ANY matches, grant access
    for schedule in schedules:
        if not schedule.get('is_active', True):
            continue
            
        if matches_schedule(schedule, check_time):
            return (True, schedule.get('name', 'Unnamed schedule'))
    
    # No schedule matched
    return (False, None)


def format_schedule_description(schedule: dict) -> str:
    """
    Format schedule rule as human-readable string.
    
    Args:
        schedule: Schedule rule dict
    
    Returns:
        Human-readable description
    
    Examples:
        Mon-Fri 08:00-16:00
        Weekends only
        First day of month 04:00-08:00
        May only, Tue/Thu/Sat 10:00-12:00
    """
    parts = []
    
    # Weekdays
    weekdays = schedule.get('weekdays')
    if weekdays:
        weekday_names = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
        if weekdays == [0, 1, 2, 3, 4]:
            parts.append("Mon-Fri")
        elif weekdays == [5, 6]:
            parts.append("Weekends")
        elif weekdays == [0, 1, 2, 3, 4, 5, 6]:
            parts.append("Every day")
        else:
            day_str = '/'.join(weekday_names[d] for d in sorted(weekdays))
            parts.append(day_str)
    
    # Months
    months = schedule.get('months')
    if months:
        month_names = ['', 'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 
                      'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
        if len(months) == 1:
            parts.append(f"{month_names[months[0]]} only")
        else:
            month_str = '/'.join(month_names[m] for m in sorted(months))
            parts.append(month_str)
    
    # Days of month
    days = schedule.get('days_of_month')
    if days:
        if days == [1]:
            parts.append("First day of month")
        elif days == list(range(1, 32)):
            pass  # All days - don't mention
        else:
            day_str = ','.join(str(d) for d in sorted(days))
            parts.append(f"Days: {day_str}")
    
    # Time range
    time_start = schedule.get('time_start')
    time_end = schedule.get('time_end')
    if time_start or time_end:
        start_str = time_start.strftime('%H:%M') if time_start else '00:00'
        end_str = time_end.strftime('%H:%M') if time_end else '23:59'
        parts.append(f"{start_str}-{end_str}")
    
    return ' '.join(parts) if parts else 'Always'


if __name__ == '__main__':
    # Test cases
    from datetime import time
    
    print("Testing schedule checker...")
    
    # Test 1: Business hours (Mon-Fri 8-16)
    schedule1 = {
        'name': 'Business hours',
        'weekdays': [0, 1, 2, 3, 4],
        'time_start': time(8, 0),
        'time_end': time(16, 0),
        'months': None,
        'days_of_month': None,
        'timezone': 'Europe/Warsaw',
        'is_active': True
    }
    
    # Monday 10:00 (should match)
    test_time1 = datetime(2026, 1, 6, 9, 0, 0, tzinfo=pytz.utc)  # 10:00 Warsaw
    result1 = matches_schedule(schedule1, test_time1)
    print(f"Mon 10:00 Warsaw: {result1} (expected: True)")
    
    # Monday 18:00 (should NOT match)
    test_time2 = datetime(2026, 1, 6, 17, 0, 0, tzinfo=pytz.utc)  # 18:00 Warsaw
    result2 = matches_schedule(schedule1, test_time2)
    print(f"Mon 18:00 Warsaw: {result2} (expected: False)")
    
    # Saturday 10:00 (should NOT match)
    test_time3 = datetime(2026, 1, 10, 9, 0, 0, tzinfo=pytz.utc)  # Sat 10:00 Warsaw
    result3 = matches_schedule(schedule1, test_time3)
    print(f"Sat 10:00 Warsaw: {result3} (expected: False)")
    
    # Test 2: First Monday of month, 04:00-08:00, May only
    schedule2 = {
        'name': 'Monthly backup',
        'weekdays': [0],  # Monday
        'time_start': time(4, 0),
        'time_end': time(8, 0),
        'months': [5],  # May
        'days_of_month': list(range(1, 8)),  # First week
        'timezone': 'Europe/Warsaw',
        'is_active': True
    }
    
    desc1 = format_schedule_description(schedule1)
    desc2 = format_schedule_description(schedule2)
    print(f"\nSchedule 1: {desc1}")
    print(f"Schedule 2: {desc2}")

"""Duration parser - converts human-readable duration strings to minutes"""
import re
from typing import Optional


def parse_duration(duration_str: str) -> Optional[int]:
    """
    Parse human-readable duration string to minutes.
    
    Supported formats:
        Simple:
            30m, 2h, 5d, 1w, 3M (months), 1y (years)
            30min, 2hours, 5days, 1week, 3months, 1year
        
        Decimal:
            2.5h (2 hours 30 min)
            1.5d (1 day 12 hours)
            0.5w (3.5 days)
        
        Combined:
            1h30m (1 hour 30 minutes)
            2d12h (2 days 12 hours)
            1w3d (1 week 3 days)
            1y6M (1 year 6 months)
    
    Args:
        duration_str: Duration string (e.g., "2h30m", "1.5d", "30min")
    
    Returns:
        Total duration in minutes, or None if parsing failed
    
    Examples:
        >>> parse_duration("30m")
        30
        >>> parse_duration("2h")
        120
        >>> parse_duration("1.5h")
        90
        >>> parse_duration("1d")
        1440
        >>> parse_duration("1w")
        10080
        >>> parse_duration("1h30m")
        90
        >>> parse_duration("2d12h30m")
        3630
        >>> parse_duration("0")
        0
        >>> parse_duration("permanent")
        0
    """
    if not duration_str:
        return 0
    
    duration_str = duration_str.strip()
    
    # Normalize month marker: 'M' alone → 'mo' to avoid conflict with 'm' (minutes)
    # Match: number followed by M (not part of longer word)
    duration_str = re.sub(r'(\d+(?:\.\d+)?)\s*M(?!\w)', r'\1mo', duration_str)
    
    duration_str = duration_str.lower()
    
    # Special cases
    if duration_str in ('0', 'permanent', 'never', 'infinity'):
        return 0
    
    # Unit conversions to minutes
    units = {
        'y': 525600,      # year (365 days)
        'year': 525600,
        'years': 525600,
        'mo': 43200,      # month (30 days) - 'mo' to avoid conflict with 'm'
        'mon': 43200,
        'month': 43200,
        'months': 43200,
        'w': 10080,       # week (7 days)
        'week': 10080,
        'weeks': 10080,
        'd': 1440,        # day (24 hours)
        'day': 1440,
        'days': 1440,
        'h': 60,          # hour
        'hour': 60,
        'hours': 60,
        'hr': 60,
        'hrs': 60,
        'm': 1,           # minute
        'min': 1,
        'mins': 1,
        'minute': 1,
        'minutes': 1,
    }
    
    # Try to match multiple components (e.g., "1h30m", "2d12h")
    # Pattern: number (optionally with decimal) followed by unit
    pattern = r'(\d+(?:\.\d+)?)\s*([a-zA-Z]+)'
    matches = re.findall(pattern, duration_str)
    
    if not matches:
        return None
    
    total_minutes = 0
    
    for value_str, unit in matches:
        value = float(value_str)
        
        # Find matching unit (case-insensitive)
        multiplier = units.get(unit.lower())
        if multiplier is None:
            # Unknown unit
            return None
        
        total_minutes += value * multiplier
    
    return int(total_minutes)


def format_duration(minutes: int) -> str:
    """
    Format minutes into human-readable duration.
    
    Args:
        minutes: Duration in minutes
    
    Returns:
        Formatted string like "2h 30m", "1d 12h", "Permanent"
    
    Examples:
        >>> format_duration(0)
        'Permanent'
        >>> format_duration(30)
        '30m'
        >>> format_duration(90)
        '1h 30m'
        >>> format_duration(1440)
        '1d'
        >>> format_duration(3630)
        '2d 12h 30m'
    """
    if minutes == 0:
        return 'Permanent'
    
    parts = []
    
    # Years
    if minutes >= 525600:
        years = minutes // 525600
        minutes %= 525600
        parts.append(f"{years}y")
    
    # Months
    if minutes >= 43200:
        months = minutes // 43200
        minutes %= 43200
        parts.append(f"{months}mo")
    
    # Weeks
    if minutes >= 10080:
        weeks = minutes // 10080
        minutes %= 10080
        parts.append(f"{weeks}w")
    
    # Days
    if minutes >= 1440:
        days = minutes // 1440
        minutes %= 1440
        parts.append(f"{days}d")
    
    # Hours
    if minutes >= 60:
        hours = minutes // 60
        minutes %= 60
        parts.append(f"{hours}h")
    
    # Minutes
    if minutes > 0:
        parts.append(f"{minutes}m")
    
    return ' '.join(parts)


if __name__ == '__main__':
    # Test cases
    test_cases = [
        ("30m", 30),
        ("2h", 120),
        ("1.5h", 90),
        ("1d", 1440),
        ("1w", 10080),
        ("1h30m", 90),
        ("2d12h30m", 3630),
        ("0", 0),
        ("permanent", 0),
        ("1y", 525600),
        ("1M", 43200),  # Capital M for month
        ("1mo", 43200),  # 'mo' for month
        ("1y6M", 525600 + 6*43200),  # 1 year 6 months
        ("2.5d", int(2.5*1440)),  # 2.5 days
    ]
    
    print("Testing duration parser:")
    for input_str, expected in test_cases:
        result = parse_duration(input_str)
        status = "✓" if result == expected else f"✗ (got {result})"
        print(f"  {input_str:15s} → {result:8d} min  {status}")
        if result:
            formatted = format_duration(result)
            print(f"  {'':15s}   {formatted}")

"""Server-owned product calendar; Vietnam day and week start at 07:00."""
from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo


def effective_day(now: datetime):
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("An aware server timestamp is required.")
    return (now.astimezone(ZoneInfo("Asia/Ho_Chi_Minh")) - timedelta(hours=7)).date()


def week_start(now: datetime):
    day = effective_day(now)
    monday = day - timedelta(days=day.weekday())
    return datetime.combine(monday, time(7), tzinfo=ZoneInfo("Asia/Ho_Chi_Minh")).astimezone(timezone.utc)

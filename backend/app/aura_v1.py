"""Approved Aura V1 policy. Historical simulation fixtures are not runtime policy."""
from bisect import bisect_right
from datetime import datetime, time, timedelta, timezone
import json
from zoneinfo import ZoneInfo

SCHEMA = "aurameme-aura-v1"
REALMS = ("Luyện Khí", "Trúc Cơ", "Kim Đan", "Nguyên Anh", "Hóa Thần", "Luyện Hư", "Hợp Thể", "Đại Thừa", "Độ Kiếp", "Phi Thăng")
THRESHOLDS = tuple(sum(10+n for n in range(1,level)) for level in range(1,101))
_POLICY = {"schema":SCHEMA,"version":1,"daily_cap":135,"checkin_xp":15,"reset_hour":7,"timezone":"Asia/Ho_Chi_Minh","max_level":100,"multipliers_enabled":False,
    "rewards":{"post_author":{"xp":10,"daily_limit":2},"reaction_actor":{"xp":1,"daily_limit":10},"reaction_author":{"xp":2,"daily_limit":20},"comment_actor":{"xp":2,"daily_limit":10},"comment_author":{"xp":3,"daily_limit":10}}}
_SNAPSHOT = json.dumps(_POLICY,sort_keys=True,separators=(",",":"),ensure_ascii=False)


def config():
    return json.loads(_SNAPSHOT)


def validate_config(value):
    if json.dumps(value,sort_keys=True,separators=(",",":"),ensure_ascii=False)!=_SNAPSHOT:
        raise ValueError("Published Aura V1 policy differs from the reviewed snapshot.")
    return value


def level_progress(total):
    if type(total) is not int or total<0:
        raise ValueError("XP must be a nonnegative integer.")
    level=min(100,bisect_right(THRESHOLDS,total))
    into=total-THRESHOLDS[level-1]
    need=10+level if level<100 else None
    return {"level":level,"realm":REALMS[(level-1)//10],"level_xp":into,"next_level_xp":need,"xp_to_next":max(0,need-into) if need else 0}


def day_window(now):
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("An aware server timestamp is required.")
    local=now.astimezone(ZoneInfo("Asia/Ho_Chi_Minh"))
    day=(local-timedelta(hours=7)).date()
    start=datetime.combine(day,time(7),tzinfo=ZoneInfo("Asia/Ho_Chi_Minh")).astimezone(timezone.utc)
    return day,start,start+timedelta(days=1)

from datetime import datetime, timezone
import pytest
from app.aura_v1 import level_progress, config, validate_config, day_window

@pytest.mark.parametrize("xp,level,into,need",[(0,1,0,11),(10,1,10,11),(11,2,0,12),(135,10,0,20),(155,11,0,21),(5831,99,0,109),(5940,100,0,None),(99999,100,94059,None)])
def test_exact_v1_curve(xp,level,into,need):
    state=level_progress(xp)
    assert (state["level"],state["level_xp"],state["next_level_xp"])==(level,into,need)
    assert state["xp_to_next"]==(need-into if need else 0)
    assert state["realm"]==("Luyện Khí" if level<=10 else "Trúc Cơ" if level<=20 else "Phi Thăng")

@pytest.mark.parametrize("xp",[-1,True,1.5])
def test_invalid_xp_refused(xp):
    with pytest.raises(ValueError):level_progress(xp)

def test_policy_is_complete_and_cannot_be_replaced_by_old_fixture():
    policy=config();assert policy["daily_cap"]==135 and policy["checkin_xp"]==15
    assert sum(row["xp"]*row["daily_limit"] for row in policy["rewards"].values())+15==135
    assert policy["multipliers_enabled"] is False
    validate_config(policy);policy["daily_cap"]=136
    with pytest.raises(ValueError):validate_config(policy)
    with pytest.raises(ValueError):validate_config({"xp":{"post":99},"daily_cap":135,"levels":[0,10]})
    assert config()["daily_cap"]==135

def test_effective_day_boundary_and_reset_window():
    before=datetime.fromisoformat("2026-11-15T06:59:59+07:00");after=datetime.fromisoformat("2026-11-15T07:00:00+07:00")
    assert str(day_window(before)[0])=="2026-11-14"
    day,start,end=day_window(after);assert str(day)=="2026-11-15"
    assert start==after.astimezone(timezone.utc) and (end-start).total_seconds()==86400
    with pytest.raises(ValueError):day_window(datetime(2026,11,15))

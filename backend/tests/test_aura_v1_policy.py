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


REALM_BOUNDARIES = [
    (1, "Luyện Khí"), (10, "Luyện Khí"),
    (11, "Trúc Cơ"), (20, "Trúc Cơ"),
    (21, "Kim Đan"), (30, "Kim Đan"),
    (31, "Nguyên Anh"), (40, "Nguyên Anh"),
    (41, "Hóa Thần"), (50, "Hóa Thần"),
    (51, "Luyện Hư"), (60, "Luyện Hư"),
    (61, "Hợp Thể"), (70, "Hợp Thể"),
    (71, "Đại Thừa"), (80, "Đại Thừa"),
    (81, "Độ Kiếp"), (90, "Độ Kiếp"),
    (91, "Phi Thăng"), (99, "Phi Thăng"), (100, "Phi Thăng"),
]


@pytest.mark.parametrize("level,expected_realm", REALM_BOUNDARIES)
def test_all_realm_boundaries_exact(level, expected_realm):
    from app.aura_v1 import THRESHOLDS, public_title_for_user, realm_for_level
    assert realm_for_level(level) == expected_realm
    state = level_progress(THRESHOLDS[level - 1])
    assert state["level"] == level
    assert state["realm"] == expected_realm
    assert public_title_for_user(level, "regular_user") == (expected_realm, expected_realm)


def test_special_titles_and_negative_level_boundaries():
    from uuid import uuid4
    from app.account_schemas import AccountPrivate, UserPublic
    from app.aura_v1 import public_title_for_user, realm_for_level, special_title_for_username
    now = datetime(2026, 11, 22, 12, 0, tzinfo=timezone.utc)
    # Admin special titles persist across all level upgrades without replacing true realm
    for level in (1, 10, 11, 79, 80, 81, 100):
        expected_realm = realm_for_level(level)
        assert public_title_for_user(level, "khang_dev") == (expected_realm, "Bá Chủ Thiên Lôi")
        assert public_title_for_user(level, "kien_dev") == (expected_realm, "Thiên Tướng Độ Ách")
        assert public_title_for_user(level, "other_admin") == (expected_realm, expected_realm)
    # Missing level never fabricates realm or title, even for special usernames
    assert public_title_for_user(None, "khang_dev") == (None, None)
    assert public_title_for_user(None, "kien_dev") == (None, None)
    assert public_title_for_user(None, "regular_user") == (None, None)
    # Invalid levels are rejected
    for bad_level in (0, -1, 101, True, 1.5, "10"):
        with pytest.raises(ValueError):
            realm_for_level(bad_level)
    # AccountPrivate omits title for normal users, includes backend-authorized title for special users
    base = dict(id=uuid4(), username="alice", email="alice@example.com", display_name="Alice", roles=["USER"], status="active")
    assert "title" not in AccountPrivate(**base, title=special_title_for_username("alice")).model_dump()
    assert AccountPrivate(**{**base, "username": "khang_dev"}, title=special_title_for_username("khang_dev")).model_dump()["title"] == "Bá Chủ Thiên Lôi"
    assert AccountPrivate(**{**base, "username": "kien_dev"}, title=special_title_for_username("kien_dev")).model_dump()["title"] == "Thiên Tướng Độ Ách"
    # UserPublic ignores forged client title/realm when level is None
    forged = UserPublic(id=uuid4(), username="khang_dev", display_name="Khang", created_at=now, level=None, realm="Phi Thăng", title="Bá Chủ Thiên Lôi").model_dump()
    assert "realm" not in forged and "title" not in forged

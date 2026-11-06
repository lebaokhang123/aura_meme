"""Draft simulations only. No HTTP routes or production reward hooks are enabled."""
from bisect import bisect_right
from datetime import datetime, timedelta, timezone
from typing import Annotated, Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, StrictBool, field_validator
from sqlalchemy import func, select, text

from app.comments import lock_public_post
from app.models import AuraLedger, Comment, Post, PostReaction, RewardPolicyVersion, User, UserProgress

Positive = Annotated[int, Field(strict=True, gt=0, le=2**31 - 1)]


class CheckinSchedule(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    xp_by_weekday: list[Positive] = Field(min_length=7, max_length=7)
    khi_by_weekday: list[Positive] = Field(min_length=7, max_length=7)
    weekly_asset_id: Annotated[UUID, Field(strict=False)] | None = None


class VaultSchedule(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    daily_free: StrictBool
    max_daily_opens: Positive
    duplicate_mode: Literal["quantity"]


class DraftPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    xp: dict[Literal["post", "reaction", "comment"], Positive]
    daily_cap: Positive
    levels: list[Annotated[int, Field(strict=True, ge=0, le=2**63 - 1)]] = Field(min_length=1, max_length=1000)
    checkin: CheckinSchedule | None = None
    vault: VaultSchedule | None = None

    @field_validator("levels")
    @classmethod
    def ascending(cls, values):
        if values[0] != 0 or any(a >= b for a, b in zip(values, values[1:])):
            raise ValueError("Draft level thresholds must start at zero and strictly increase.")
        return values


def simulation_only(db, now):
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("Simulation requires a timezone-aware server timestamp.")
    if db.execute(text("SELECT current_database(), current_schema()")).one() != ("aurameme_test", "public"):
        raise ValueError("Draft reward simulation is allowed only on isolated aurameme_test/public.")
    return now.astimezone(timezone.utc)


def lock_users(db, identities):
    users = list(db.scalars(select(User).where(User.id.in_(identities)).order_by(User.id).with_for_update().execution_options(populate_existing=True)))
    if {user.id for user in users} != set(identities) or any(user.status != "active" for user in users):
        raise ValueError("Reward participants must be active accounts.")


def policy_config(db, policy_id, now):
    policy = db.scalar(select(RewardPolicyVersion).where(RewardPolicyVersion.id == policy_id).with_for_update(read=True).execution_options(populate_existing=True))
    if policy is None or policy.status != "draft" or policy.effective_at > now:
        raise ValueError("An effective draft fixture policy is required; runtime rewards remain disabled.")
    return DraftPolicy.model_validate(policy.config_json)


def update_progress(db, progress, owner, base, bonus, config, now):
    if progress is None:
        progress = UserProgress(user_id=owner, aura_xp_earned=0, aura_xp_bonus=0,
            level_cached=1, fair_level_cached=1, streak_days=0, last_checkin_day=None, updated_at=now)
        db.add(progress)
    earned, extra = progress.aura_xp_earned + base, progress.aura_xp_bonus + bonus
    if earned < 0 or extra < 0:
        raise ValueError("Reversal would make progress negative; preserve data for review.")
    progress.aura_xp_earned, progress.aura_xp_bonus = earned, extra
    progress.level_cached = bisect_right(config.levels, earned + extra)
    progress.fair_level_cached = bisect_right(config.levels, earned)
    progress.updated_at = now
    db.flush()


def simulate_reward(db, policy_id: UUID, kind: str, source_id: UUID, actor_id: UUID, now: datetime):
    """Caller owns the transaction; fixture cap uses UTC calendar days, not a product decision."""
    now = simulation_only(db, now)
    with db.begin_nested():
        return _reward(db, policy_id, kind, source_id, actor_id, now)


def _reward(db, policy_id, kind, source_id, actor_id, now):
    if kind not in {"post", "reaction", "comment"}:
        raise ValueError("Unsupported draft source event.")
    comment = db.get(Comment, source_id) if kind == "comment" else None
    post = db.get(Post, comment.post_id if comment else source_id)
    if post is None or (kind == "comment" and comment is None):
        raise ValueError("Reward source does not exist.")
    owner = post.author_id
    lock_users(db, {owner, actor_id})
    progress = db.scalar(select(UserProgress).where(UserProgress.user_id == owner).with_for_update().execution_options(populate_existing=True))
    config = policy_config(db, policy_id, now)
    event_key = f"{kind}:{source_id}" + (":" + str(actor_id) if kind == "reaction" else "")
    existing = db.scalar(select(AuraLedger).where(AuraLedger.user_id == owner, AuraLedger.event_key == event_key))
    if existing is not None:
        if existing.source_actor_id != actor_id:
            raise ValueError("Retry actor does not match the server event.")
        return existing
    lock_public_post(db, post.id)
    if post.author_id != owner:
        raise ValueError("Reward source owner changed; retry from fresh server data.")
    if post.created_at > now or (kind == "post" and actor_id != owner) or (kind != "post" and actor_id == owner):
        raise ValueError("Source actor is not eligible for this draft reward.")
    if kind == "reaction" and db.get(PostReaction, (post.id, actor_id)) is None:
        raise ValueError("A server-confirmed reaction is required.")
    if kind == "comment":
        comment = db.scalar(select(Comment).where(Comment.id == source_id).with_for_update(read=True).execution_options(populate_existing=True))
        if comment is None or comment.author_id != actor_id or comment.post_id != post.id or comment.status != "visible" or comment.deleted_at is not None or comment.created_at > now:
            raise ValueError("Comment source is not eligible.")
    amount = config.xp.get(kind)
    if amount is None:
        raise ValueError("Draft policy does not define this event.")
    start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    used = db.scalar(select(func.coalesce(func.sum(AuraLedger.base_xp), 0)).where(AuraLedger.user_id == owner,
        AuraLedger.base_xp > 0, AuraLedger.occurred_at >= start, AuraLedger.occurred_at < start + timedelta(days=1)))
    if used + amount > config.daily_cap:
        raise ValueError("Draft simulation cap reached.")
    entry = AuraLedger(id=uuid4(), user_id=owner, event_key=event_key, event_type=kind,
        source_actor_id=actor_id, source_post_id=post.id, source_comment_id=source_id if kind == "comment" else None,
        policy_id=policy_id, base_xp=amount, bonus_xp=0, tier_at_event="FREE", multiplier_at_event=1,
        reverses_id=None, occurred_at=now)
    db.add(entry)
    update_progress(db, progress, owner, amount, 0, config, now)
    return entry


def simulate_reversal(db, entry_id: UUID, now: datetime):
    now = simulation_only(db, now)
    with db.begin_nested():
        return _reversal(db, entry_id, now)


def _reversal(db, entry_id, now):
    original = db.get(AuraLedger, entry_id)
    if original is None or original.event_type == "reversal":
        raise ValueError("An original reward is required.")
    lock_users(db, {original.user_id})
    progress = db.scalar(select(UserProgress).where(UserProgress.user_id == original.user_id).with_for_update().execution_options(populate_existing=True))
    config = policy_config(db, original.policy_id, now)
    original = db.scalar(select(AuraLedger).where(AuraLedger.id == entry_id).with_for_update(read=True).execution_options(populate_existing=True))
    existing = db.scalar(select(AuraLedger).where(AuraLedger.reverses_id == entry_id))
    if existing is not None:
        return existing
    if progress is None or original.occurred_at > now:
        raise ValueError("Original progress/time is inconsistent; preserve data for review.")
    entry = AuraLedger(id=uuid4(), user_id=original.user_id, event_key="reversal:" + str(entry_id), event_type="reversal",
        source_actor_id=original.source_actor_id, source_post_id=original.source_post_id, source_comment_id=original.source_comment_id,
        policy_id=original.policy_id, base_xp=-original.base_xp, bonus_xp=-original.bonus_xp,
        tier_at_event=original.tier_at_event, multiplier_at_event=original.multiplier_at_event, reverses_id=entry_id, occurred_at=now)
    db.add(entry)
    update_progress(db, progress, original.user_id, entry.base_xp, entry.bonus_xp, config, now)
    return entry

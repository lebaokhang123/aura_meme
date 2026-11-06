"""Read-only P1 views; missing policy/state is NOT_READY, never invented balances."""
from bisect import bisect_right
from datetime import datetime, timedelta, timezone
from typing import Literal
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, Field, ValidationError
from sqlalchemy import func, select

from app.account_schemas import UserPublic
from app.aura import DraftPolicy
from app.auth_schemas import ErrorResponse
from app.blog import page_rows
from app.blog_schemas import Pagination
from app.models import AuraLedger, Profile, RewardPolicyVersion, User, UserProgress, Wallet
from app.permissions import require_authenticated_user
from app.security import AuthError

router = APIRouter(prefix="/api/v1", tags=["Aura"])
ERRORS = {code: {"model": ErrorResponse} for code in (422, 429, 500, 503)}


class AuraProgress(BaseModel):
    earned_xp: int = Field(ge=0)
    bonus_xp: int = Field(ge=0)
    total_xp: int = Field(ge=0)
    level: int = Field(ge=1)
    fair_level: int = Field(ge=1)
    streak_days: int = Field(ge=0)
    khi_van_balance: int = Field(ge=0)


class LeaderboardEntry(BaseModel):
    rank: int = Field(ge=1)
    user: UserPublic
    earned_xp: int = Field(ge=0)


class LeaderboardPage(BaseModel):
    items: list[LeaderboardEntry]
    pagination: Pagination


def not_ready():
    raise AuthError(503, "NOT_READY", "Aura policy or account state is not ready.")


def read_policy(db, now):
    policy = db.scalar(select(RewardPolicyVersion).where(RewardPolicyVersion.status == "published",
        RewardPolicyVersion.effective_at <= now).order_by(RewardPolicyVersion.effective_at.desc(), RewardPolicyVersion.version.desc()).limit(1))
    if policy is None:
        not_ready()
    try:
        return DraftPolicy.model_validate(policy.config_json)
    except ValidationError:
        not_ready()


def week_start(now: datetime):
    shifted = now.astimezone(ZoneInfo("Asia/Ho_Chi_Minh")) - timedelta(hours=7)
    return (shifted - timedelta(days=shifted.weekday())).replace(hour=7, minute=0, second=0, microsecond=0).astimezone(timezone.utc)


@router.get("/aura/progress", response_model=AuraProgress, operation_id="getAuraProgress",
            responses=ERRORS | {code: {"model": ErrorResponse} for code in (401, 403)})
def progress(request: Request, account=Depends(require_authenticated_user, scope="function")):
    db, owner = account.db, account.user.id
    now = request.app.state.auth.now()
    config = read_policy(db, now)
    state, wallet = db.get(UserProgress, owner), db.get(Wallet, owner)
    if state is None or wallet is None:
        not_ready()
    earned, bonus, latest = db.execute(select(func.coalesce(func.sum(AuraLedger.base_xp), 0),
        func.coalesce(func.sum(AuraLedger.bonus_xp), 0), func.max(AuraLedger.occurred_at)).where(AuraLedger.user_id == owner)).one()
    if (latest is not None and latest > now) or (earned, bonus) != (state.aura_xp_earned, state.aura_xp_bonus):
        not_ready()
    return AuraProgress(earned_xp=earned, bonus_xp=bonus, total_xp=earned + bonus,
        level=bisect_right(config.levels, earned + bonus), fair_level=bisect_right(config.levels, earned),
        streak_days=state.streak_days, khi_van_balance=wallet.khi_van_balance)


@router.get("/leaderboard", response_model=LeaderboardPage, operation_id="getLeaderboard", responses=ERRORS)
def leaderboard(request: Request, page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100),
                period: Literal["all", "week"] = "all"):
    with request.app.state.auth_session_factory() as db:
        now = request.app.state.auth.now()
        read_policy(db, now)
        points = func.sum(AuraLedger.base_xp)
        scores = select(AuraLedger.user_id, points.label("score")).where(AuraLedger.occurred_at <= now)
        if period == "week":
            scores = scores.where(AuraLedger.occurred_at >= week_start(now))
        scores = scores.group_by(AuraLedger.user_id).having(points > 0).subquery()
        ranked = select(User.id.label("user_id"), scores.c.score,
            func.row_number().over(order_by=(scores.c.score.desc(), User.id)).label("rank")).join(
                scores, scores.c.user_id == User.id).join(Profile, Profile.user_id == User.id).where(User.status == "active").subquery()
        query = select(User, Profile, ranked.c.rank, ranked.c.score).join(Profile, Profile.user_id == User.id).join(
            ranked, ranked.c.user_id == User.id).order_by(ranked.c.rank)
        rows, pagination = page_rows(db, query, page, page_size)
        return LeaderboardPage(items=[LeaderboardEntry(rank=rank, earned_xp=score,
            user=UserPublic(id=user.id, username=user.username, display_name=profile.display_name,
                created_at=user.created_at, bio=profile.bio, avatar_url=None)) for user, profile, rank, score in rows], pagination=pagination)

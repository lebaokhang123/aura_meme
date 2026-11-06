"""Draft-only claim mechanics; runtime grant and weekly asset delivery remain disabled."""
from datetime import date, datetime, timedelta
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import Date, Integer, cast, func, literal, select

from app.aura import lock_users, policy_config, simulation_only, update_progress
from app.aura_clock import effective_day
from app.auth import CSRF_HEADER, ERRORS
from app.auth_schemas import ErrorResponse
from app.inventory_grants import weekly_grant
from app.models import AuraLedger, DailyCheckin, UserProgress, Wallet, WalletTransaction
from app.permissions import require_account_csrf
from app.security import AuthError

router = APIRouter(prefix="/api/v1/aura", tags=["Aura"])


class CheckInResult(BaseModel):
    effective_day: date
    already_checked_in: bool
    earned_xp_delta: int = Field(ge=0)
    bonus_xp_delta: int = Field(ge=0)
    khi_van_delta: int = Field(ge=0)
    streak_days: int = Field(ge=0)


@router.post("/check-in", response_model=CheckInResult, operation_id="dailyCheckin",
             responses=ERRORS | {503: {"model": ErrorResponse}}, openapi_extra=CSRF_HEADER)
def claim(account=Depends(require_account_csrf)):
    # No approved economic policy/weekly catalog: never wire the simulator into runtime.
    raise AuthError(503, "NOT_READY", "Check-in rewards are not ready.")


def completed_week(db, owner, day):
    monday = day - timedelta(days=day.weekday())
    return db.scalar(select(func.count()).select_from(DailyCheckin).where(DailyCheckin.user_id == owner,
        DailyCheckin.effective_day >= monday, DailyCheckin.effective_day < monday + timedelta(days=7),
        DailyCheckin.effective_day <= day)) == 7


def streak_length(db, owner, last_day):
    if last_day is None:
        return 0
    dates = select(DailyCheckin.effective_day.label("day"),
        func.row_number().over(order_by=DailyCheckin.effective_day.desc()).label("ordinal")).where(
            DailyCheckin.user_id == owner, DailyCheckin.effective_day <= last_day).subquery()
    expected = literal(last_day, Date) - cast(dates.c.ordinal - 1, Integer)
    return db.scalar(select(func.count()).select_from(dates).where(dates.c.day == expected))


def simulate_checkin(db, policy_id: UUID, owner: UUID, now: datetime):
    now = simulation_only(db, now)
    with db.begin_nested():
        return _checkin(db, policy_id, owner, now)


def receipt_result(db, receipt, streak, already):
    xp = db.get(AuraLedger, receipt.aura_ledger_id)
    money = db.get(WalletTransaction, receipt.wallet_transaction_id)
    key = "checkin:" + receipt.effective_day.isoformat()
    if (xp is None or money is None or xp.user_id != receipt.user_id or money.user_id != receipt.user_id
        or xp.event_type != "checkin" or money.reason != "checkin" or xp.event_key != key or money.event_key != key
        or xp.policy_id != money.policy_id or xp.occurred_at != receipt.claimed_at or money.created_at != receipt.claimed_at):
        raise ValueError("Check-in receipt bindings are inconsistent; preserve data for review.")
    return CheckInResult(effective_day=receipt.effective_day, already_checked_in=already,
        earned_xp_delta=xp.base_xp, bonus_xp_delta=xp.bonus_xp, khi_van_delta=money.delta_khi_van, streak_days=streak)


def _checkin(db, policy_id, owner, now):
    day = effective_day(now)
    lock_users(db, {owner})
    progress = db.scalar(select(UserProgress).where(UserProgress.user_id == owner).with_for_update().execution_options(populate_existing=True))
    wallet = db.scalar(select(Wallet).where(Wallet.user_id == owner).with_for_update().execution_options(populate_existing=True))
    earned, bonus, latest = db.execute(select(func.coalesce(func.sum(AuraLedger.base_xp), 0),
        func.coalesce(func.sum(AuraLedger.bonus_xp), 0), func.max(AuraLedger.occurred_at)).where(AuraLedger.user_id == owner)).one()
    balance, last_money = db.execute(select(func.coalesce(func.sum(WalletTransaction.delta_khi_van), 0),
        func.max(WalletTransaction.created_at)).where(WalletTransaction.user_id == owner)).one()
    last_day = db.scalar(select(func.max(DailyCheckin.effective_day)).where(DailyCheckin.user_id == owner))
    if ((earned, bonus) != ((progress.aura_xp_earned, progress.aura_xp_bonus) if progress else (0, 0))
        or balance != (wallet.khi_van_balance if wallet else 0)
        or last_day != (progress.last_checkin_day if progress else None)
        or streak_length(db, owner, last_day) != (progress.streak_days if progress else 0)
        or (last_day is not None and last_day > day)):
        raise ValueError("Check-in cache or server time is inconsistent; preserve data for review.")
    existing = db.get(DailyCheckin, (owner, day))
    if existing is not None:
        return receipt_result(db, existing, progress.streak_days, True)
    if any(stamp is not None and stamp > now for stamp in (latest, last_money)):
        raise ValueError("Check-in server time is inconsistent; preserve data for review.")
    config = policy_config(db, policy_id, now)
    if config.checkin is None:
        raise ValueError("An explicit draft check-in schedule is required.")
    xp, money = config.checkin.xp_by_weekday[day.weekday()], config.checkin.khi_by_weekday[day.weekday()]
    streak = progress.streak_days + 1 if last_day == day - timedelta(days=1) else 1
    if wallet is None:
        wallet = Wallet(user_id=owner, khi_van_balance=0, updated_at=now)
        db.add(wallet)
        db.flush()
    key = "checkin:" + day.isoformat()
    entry = AuraLedger(id=uuid4(), user_id=owner, event_key=key, event_type="checkin", source_actor_id=None,
        source_post_id=None, source_comment_id=None, policy_id=policy_id, base_xp=xp, bonus_xp=0,
        tier_at_event="FREE", multiplier_at_event=1, reverses_id=None, occurred_at=now)
    credit = WalletTransaction(id=uuid4(), user_id=owner, event_key=key, delta_khi_van=money,
        reason="checkin", policy_id=policy_id, reverses_id=None, created_at=now)
    db.add_all([entry, credit])
    db.flush()
    update_progress(db, progress, owner, xp, 0, config, now)
    progress = db.get(UserProgress, owner)
    progress.last_checkin_day, progress.streak_days = day, streak
    wallet.khi_van_balance += money
    wallet.updated_at = now
    receipt = DailyCheckin(user_id=owner, effective_day=day, aura_ledger_id=entry.id, wallet_transaction_id=credit.id, claimed_at=now)
    db.add(receipt)
    db.flush()
    if config.checkin.weekly_asset_id is not None:
        weekly_grant(db, owner, config.checkin.weekly_asset_id, policy_id, day, now)
    return receipt_result(db, receipt, streak, False)

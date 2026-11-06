"""Atomic draft open simulator; HTTP runtime remains NOT_READY regardless of stored fixtures."""
from dataclasses import dataclass
from typing import Annotated
from uuid import UUID, uuid4
import secrets

from fastapi import APIRouter, Depends, Header
from pydantic import BaseModel, Field
from sqlalchemy import func, select

from app.aura import lock_users, policy_config, simulation_only
from app.aura_clock import effective_day
from app.auth import CSRF_HEADER, ERRORS
from app.auth_schemas import ErrorResponse
from app.inventory import Asset
from app.inventory_grants import grant_item, inventory_state
from app.models import AuraLedger, CaseDefinition, CaseLootTable, CaseOpen, InventoryGrant, UserProgress, Wallet, WalletTransaction
from app.permissions import require_account_csrf
from app.security import AuthError
from app.vault import choose_band, draw, load_version

router = APIRouter(prefix='/api/v1/vault', tags=['Vault'])


class CaseOpenResult(BaseModel):
    open_id: UUID
    case_id: UUID
    reward: Asset
    cost_khi_van: int = Field(ge=0)
    khi_van_balance: int = Field(ge=0)
    already_processed: bool


@router.post('/cases/{case_id}/open', response_model=CaseOpenResult, operation_id='openCase',
             responses=ERRORS | {503: {'model': ErrorResponse}}, openapi_extra=CSRF_HEADER)
def open_case(case_id: UUID, idempotency_key: Annotated[str, Header(alias='Idempotency-Key', min_length=12, max_length=128)],
              account=Depends(require_account_csrf)):
    if not idempotency_key.strip():
        raise AuthError(422, 'VALIDATION_ERROR', 'Idempotency key must not be blank.')
    # Owner approved readiness response, not economic activation or assets.
    raise AuthError(503, 'NOT_READY', 'Case opening is not ready.')


@dataclass(frozen=True)
class OpenReceipt:
    open_id: UUID
    case_id: UUID
    reward_asset_id: UUID
    cost_khi_van: int
    khi_van_balance: int
    already_processed: bool


def simulate_open(db, owner, case_id, key, now, *, randbelow=secrets.randbelow):
    now = simulation_only(db, now)
    if not isinstance(key, str) or not 12 <= len(key) <= 128 or not key.strip() or '\x00' in key:
        raise ValueError('Invalid draft idempotency key.')
    with db.begin_nested():
        return _open(db, owner, case_id, key, now, randbelow)


def _open(db, owner, case_id, key, now, randbelow):
    lock_users(db, {owner})
    progress = db.scalar(select(UserProgress).where(UserProgress.user_id == owner).with_for_update().execution_options(populate_existing=True))
    wallet = db.scalar(select(Wallet).where(Wallet.user_id == owner).with_for_update().execution_options(populate_existing=True))
    earned, bonus, latest = db.execute(select(func.coalesce(func.sum(AuraLedger.base_xp),0), func.coalesce(func.sum(AuraLedger.bonus_xp),0),
        func.max(AuraLedger.occurred_at)).where(AuraLedger.user_id == owner)).one()
    balance, last_money = db.execute(select(func.coalesce(func.sum(WalletTransaction.delta_khi_van),0),
        func.max(WalletTransaction.created_at)).where(WalletTransaction.user_id == owner)).one()
    if ((earned,bonus) != ((progress.aura_xp_earned,progress.aura_xp_bonus) if progress else (0,0))
        or balance != (wallet.khi_van_balance if wallet else 0)):
        raise ValueError('Progress/wallet cache or server time is inconsistent; preserve data for review.')
    existing = db.scalar(select(CaseOpen).where(CaseOpen.user_id == owner, CaseOpen.request_key == key))
    if existing is not None:
        if existing.case_id != case_id:
            raise ValueError('Idempotency key conflicts with a different case.')
        grant = db.scalar(select(InventoryGrant).where(InventoryGrant.case_open_id == existing.id))
        if grant is None or grant.user_id != owner or grant.asset_id != existing.reward_asset_id:
            raise ValueError('Opening receipt is missing its bound grant; preserve data for review.')
        inventory_state(db, owner, existing.reward_asset_id)
        return OpenReceipt(existing.id, case_id, existing.reward_asset_id, existing.cost_khi_van, balance, True)
    if any(stamp is not None and stamp > now for stamp in (latest,last_money)):
        raise ValueError('Case server time moved backwards.')
    day = effective_day(now)
    latest_open = db.scalar(select(func.max(CaseOpen.created_at)).where(CaseOpen.user_id == owner))
    if latest_open is not None and latest_open > now:
        raise ValueError('Case server time moved backwards.')
    case = db.scalar(select(CaseDefinition).where(CaseDefinition.id == case_id).with_for_update(read=True).execution_options(populate_existing=True))
    if case is None or case.slug != 'common' or case.status != 'draft':
        raise ValueError('An isolated draft common case is required.')
    version = db.scalar(select(func.max(CaseLootTable.odds_version)).where(CaseLootTable.case_id == case.id, CaseLootTable.status == 'draft'))
    pools = load_version(db, case.id, version, now, 'draft')
    pool = choose_band(pools, earned)
    config = policy_config(db, pool.policy_id, now)
    if config.vault is None:
        raise ValueError('An explicit draft quota/duplicate policy is required.')
    used = db.scalar(select(func.count()).select_from(CaseOpen).where(CaseOpen.user_id == owner, CaseOpen.case_id == case.id, CaseOpen.effective_day == day))
    if used >= config.vault.max_daily_opens:
        raise ValueError('Draft daily quota reached.')
    free_used = db.scalar(select(CaseOpen.id).where(CaseOpen.user_id == owner, CaseOpen.case_id == case.id,
        CaseOpen.effective_day == day, CaseOpen.is_daily_free.is_(True)))
    free = config.vault.daily_free and free_used is None
    cost = 0 if free else case.cost_khi_van
    if balance < cost:
        raise ValueError('Insufficient draft wallet balance.')
    if wallet is None:
        wallet = Wallet(user_id=owner, khi_van_balance=0, updated_at=now)
        db.add(wallet)
        db.flush()
    asset_id, trace = draw(pool, randbelow=randbelow)
    opening_id, debit_id = uuid4(), None
    if cost > 0:
        debit_id = uuid4()
        db.add(WalletTransaction(id=debit_id,user_id=owner,event_key='case:'+str(opening_id),delta_khi_van=-cost,
            reason='case_open',policy_id=pool.policy_id,reverses_id=None,created_at=now))
        wallet.khi_van_balance -= cost
        wallet.updated_at = now
        db.flush()
    opening = CaseOpen(id=opening_id,user_id=owner,request_key=key,case_id=case.id,loot_table_id=pool.id,
        reward_asset_id=asset_id,earned_xp_at_open=earned,cost_khi_van=cost,wallet_transaction_id=debit_id,
        is_daily_free=free,effective_day=day,decision_trace=trace,created_at=now)
    db.add(opening)
    db.flush()
    grant_item(db,owner,asset_id,pool.policy_id,'case:'+str(opening_id),'case_open',now,opening_id)
    return OpenReceipt(opening_id,case.id,asset_id,cost,wallet.khi_van_balance,False)

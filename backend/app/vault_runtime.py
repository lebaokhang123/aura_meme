"""Opt-in free Vault; isolated from legacy economic simulators and activation tooling."""
from datetime import datetime
from math import ceil
from typing import Literal
from uuid import UUID, uuid4
import secrets

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel
from sqlalchemy import and_, func, select, text
from sqlalchemy.orm import undefer

from app.aura_clock import effective_day
from app.auth import ERRORS
from app.auth_schemas import ErrorResponse
from app.blog import page_rows
from app.blog_schemas import Pagination
from app.inventory import Asset, Slot, asset_dto, ready_asset
from app.inventory_grants import _grant_item, inventory_state
from app.models import (AssetItem, AuraLedger, CaseDefinition, CaseLootRarity, CaseLootTable,
                        CaseOpen, CasePoolItem, InventoryGrant, RewardPolicyVersion,
                        UserEquipment, UserInventory, Wallet)
from app.permissions import require_authenticated_user
from app.security import AuthError
from app.catalog_rights import reviewed_source_rights_sql
from app.vault import DrawPool, RARITIES, draw
from app.vault_open import CaseOpenResult
from app.vault_v1_policy import EFFECT_KEYS, FreeVaultPolicy, WEIGHTS, next_open_at

router = APIRouter(prefix='/api/v1', tags=['Vault'])
RUNTIME_ERRORS = ERRORS | {404:{'model':ErrorResponse},503:{'model':ErrorResponse}}


def runtime_enabled(request):
    return bool(getattr(getattr(request.app.state, 'vault', None), 'vault_runtime_enabled', False))


def schema_ready(db):
    return list(db.scalars(text('SELECT version_num FROM alembic_version'))) == ['0012_aura_v1']


def require_schema(db):
    if not schema_ready(db):
        raise AuthError(503, 'NOT_READY', 'Vault V1 schema is not ready.')


def require_enabled(request, db):
    if not runtime_enabled(request):
        raise AuthError(503, 'NOT_READY', 'Vault V1 is not enabled.')
    require_schema(db)


def valid_key(key):
    if not isinstance(key, str) or not 12 <= len(key) <= 128 or not key.strip() or '\x00' in key:
        raise AuthError(422, 'VALIDATION_ERROR', 'Invalid idempotency key.')
    return key


def ready_runtime_asset(asset, kind):
    return (ready_asset(asset) and asset.kind == kind and bool(asset.display_name and asset.display_name.strip())
            and asset.source_rights.get('name_review_status') == 'approved'
            and ((kind == 'avatar' and asset.effect_key is None)
                 or (kind == 'background' and asset.effect_key == EFFECT_KEYS[RARITIES.index(asset.rarity)])))


def load_runtime_pool(db, case, now):
    if case.runtime_kind not in ('avatar', 'background') or case.status != 'active' or case.cost_khi_van != 0:
        raise ValueError('A free active runtime case is required.')
    version = db.scalar(select(func.max(CaseLootTable.odds_version)).where(
        CaseLootTable.case_id == case.id, CaseLootTable.status == 'published', CaseLootTable.active_from <= now))
    tables = list(db.scalars(select(CaseLootTable).where(CaseLootTable.case_id == case.id,
        CaseLootTable.odds_version == version).with_for_update(read=True).execution_options(populate_existing=True)))
    if len(tables) != 1:
        raise ValueError('V1 requires exactly one unbounded band.')
    table = tables[0]
    if (table.status != 'published' or table.active_from > now or table.band_no != 1
            or table.min_earned_xp != 0 or table.max_earned_xp is not None):
        raise ValueError('V1 cannot use XP bands or future odds.')
    policy = db.scalar(select(RewardPolicyVersion).where(RewardPolicyVersion.id == table.policy_id).with_for_update(read=True))
    if policy is None or policy.status != 'published' or policy.effective_at > now:
        raise ValueError('Published V1 policy is required.')
    config = FreeVaultPolicy.model_validate(policy.config_json)
    weights = dict(db.execute(select(CaseLootRarity.rarity, CaseLootRarity.weight_bps).where(
        CaseLootRarity.loot_table_id == table.id)).all())
    if weights != dict(zip(RARITIES, WEIGHTS)):
        raise ValueError('V1 odds must match the fixed five rarity weights.')
    buckets = {rarity: [] for rarity in RARITIES}
    rows = db.execute(select(CasePoolItem, AssetItem).join(AssetItem, AssetItem.id == CasePoolItem.asset_id).where(
        CasePoolItem.loot_table_id == table.id).options(undefer(AssetItem.display_name), undefer(AssetItem.effect_key))
        .order_by(CasePoolItem.asset_id).with_for_update(read=True).execution_options(populate_existing=True))
    for item, asset in rows:
        if (not ready_runtime_asset(asset, case.runtime_kind) or asset.rarity != item.rarity or item.item_weight != 1
                or (config.catalog_manifest_sha256 is not None
                    and asset.source_rights.get('manifest_sha256') != config.catalog_manifest_sha256)):
            raise ValueError('V1 pool contains an unapproved, mixed-kind or nonuniform item.')
        buckets[item.rarity].append((asset.id, 1))
    if any(not bucket for bucket in buckets.values()):
        raise ValueError('Each V1 rarity needs approved items; never redistribute odds.')
    return DrawPool(table.id, table.policy_id, version, 0, None, WEIGHTS,
                    tuple(tuple(buckets[rarity]) for rarity in RARITIES))


def runtime_history(db, owner):
    # shortcut: indexed history COUNT grows per user, use transactional state only after measured need.
    return db.execute(select(func.count(), func.max(CaseOpen.created_at)).where(
        CaseOpen.user_id == owner, CaseOpen.decision_trace['runtime'].astext == 'free-vault-v1')).one()


def receipt_reward(db, opening, request):
    asset = db.scalar(select(AssetItem).where(AssetItem.id == opening.reward_asset_id).options(
        undefer(AssetItem.display_name), undefer(AssetItem.effect_key)))
    if asset is None:
        raise AuthError(503, 'NOT_READY', 'Stored reward reference is unavailable.')
    if ready_asset(asset):
        return asset_dto(asset, request, metadata=True)
    return Asset(id=asset.id, slug=asset.slug, kind=asset.kind, rarity=asset.rarity,
                 display_name=asset.display_name or asset.slug, effect_key=None, media_url=None, available=False)


def replay_receipt(db, owner, opening):
    grant = db.scalar(select(InventoryGrant).where(InventoryGrant.case_open_id == opening.id))
    if (grant is None or grant.user_id != owner or grant.asset_id != opening.reward_asset_id
            or grant.quantity != 1 or grant.event_key != 'case:' + str(opening.id)):
        raise AuthError(503, 'NOT_READY', 'Stored receipt and inventory grant are inconsistent.')
    try:
        inventory_state(db, owner, opening.reward_asset_id)
    except ValueError:
        raise AuthError(503, 'NOT_READY', 'Stored inventory is inconsistent; preserve it for review.') from None


def receipt_result(db, owner, opening, request, already_processed):
    count, latest = runtime_history(db, owner)
    balance = db.scalar(select(Wallet.khi_van_balance).where(Wallet.user_id == owner))
    return CaseOpenResult(open_id=opening.id, case_id=opening.case_id,
        reward=receipt_reward(db, opening, request), cost_khi_van=opening.cost_khi_van,
        khi_van_balance=balance if balance is not None else 0, already_processed=already_processed,
        next_open_at=next_open_at(latest, count))


def open_runtime(request, account, case_id, key, *, randbelow=secrets.randbelow):
    db, owner = account.db, account.user.id  # Session dependency already holds the owner row lock.
    key = valid_key(key)
    # Revision check references only the old alembic_version table, never new columns on 0010.
    require_schema(db)
    existing = db.scalar(select(CaseOpen).where(CaseOpen.user_id == owner, CaseOpen.request_key == key))
    if existing is not None:
        if existing.case_id != case_id:
            raise AuthError(409, 'IDEMPOTENCY_CONFLICT', 'Idempotency key belongs to a different case.')
        if existing.decision_trace.get('runtime') != 'free-vault-v1':
            raise AuthError(409, 'IDEMPOTENCY_CONFLICT', 'Idempotency key belongs to a legacy opening.')
        replay_receipt(db, owner, existing)
        return receipt_result(db, owner, existing, request, True)
    require_enabled(request, db)
    now = request.app.state.auth.now()
    count, latest = runtime_history(db, owner)
    if latest is not None and latest > now:
        raise AuthError(503, 'NOT_READY', 'Server opening time is inconsistent.')
    available_at = next_open_at(latest, count)
    if available_at is not None and now < available_at:
        raise AuthError(429, 'COOLDOWN', 'Please wait before opening another case.',
                        retry_after=max(1, ceil((available_at-now).total_seconds())),
                        details={'next_open_at': available_at.isoformat().replace('+00:00','Z')})
    case = db.scalar(select(CaseDefinition).where(CaseDefinition.id == case_id).options(
        undefer(CaseDefinition.runtime_kind)).with_for_update(read=True).execution_options(populate_existing=True))
    if case is None or case.runtime_kind is None:
        raise AuthError(404, 'NOT_FOUND', 'Runtime case not available.')
    try:
        pool = load_runtime_pool(db, case, now)
    except ValueError:
        raise AuthError(503, 'NOT_READY', 'This case needs a complete approved catalog and policy.') from None
    asset_id, trace = draw(pool, randbelow=randbelow)
    # Read-only compatibility snapshot for 0009's trigger; XP never selects odds or changes here.
    earned = db.scalar(select(func.coalesce(func.sum(AuraLedger.base_xp), 0)).where(
        AuraLedger.user_id == owner, AuraLedger.occurred_at <= now))
    opening = CaseOpen(id=uuid4(), user_id=owner, request_key=key, case_id=case.id, loot_table_id=pool.id,
        reward_asset_id=asset_id, earned_xp_at_open=earned, cost_khi_van=0, wallet_transaction_id=None,
        is_daily_free=False, effective_day=effective_day(now), decision_trace=trace | {'runtime': 'free-vault-v1'}, created_at=now)
    db.add(opening)
    db.flush()
    try:
        _grant_item(db, owner, asset_id, pool.policy_id, 'case:'+str(opening.id), 'case_open', now, opening.id)
    except ValueError:
        raise AuthError(503, 'NOT_READY', 'Inventory is inconsistent; preserve it for review.') from None
    return receipt_result(db, owner, opening, request, False)


class CatalogEntry(BaseModel):
    asset: Asset
    owned: bool


class CatalogPage(BaseModel):
    items: list[CatalogEntry]
    pagination: Pagination


@router.get('/catalog', response_model=CatalogPage, operation_id='listCatalog', responses=RUNTIME_ERRORS)
def catalog(request: Request, kind: Literal['avatar', 'background'] | None = None,
            rarity: Literal['D','C','B','A','S'] | None = None, q: str = Query('', max_length=100),
            page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100),
            account=Depends(require_authenticated_user, scope='function')):
    require_enabled(request, account.db)
    if "\x00" in q:
        raise AuthError(422, "VALIDATION_ERROR", "Invalid catalog search.")
    query = select(AssetItem, UserInventory.asset_id).outerjoin(UserInventory, and_(
        UserInventory.asset_id == AssetItem.id, UserInventory.user_id == account.user.id,
        UserInventory.quantity > 0)).where(AssetItem.active.is_(True),
        reviewed_source_rights_sql(AssetItem.source_rights), AssetItem.kind.in_(('avatar','background')))
    if kind:
        query = query.where(AssetItem.kind == kind)
    if rarity:
        query = query.where(AssetItem.rarity == rarity)
    if q.strip():
        query = query.where(func.coalesce(AssetItem.display_name, AssetItem.slug).icontains(q.strip(), autoescape=True))
    query = query.options(undefer(AssetItem.display_name), undefer(AssetItem.effect_key)).order_by(
        func.coalesce(AssetItem.display_name, AssetItem.slug), AssetItem.id)
    rows, pagination = page_rows(account.db, query, page, page_size)
    return CatalogPage(items=[CatalogEntry(asset=asset_dto(asset, request, metadata=True), owned=owned is not None)
                              for asset, owned in rows], pagination=pagination)


class EquippedItem(BaseModel):
    slot_kind: Slot
    asset: Asset


class EquipmentPage(BaseModel):
    items: list[EquippedItem]


@router.get('/inventory/equipment', response_model=EquipmentPage, operation_id='getEquipment', responses=RUNTIME_ERRORS)
def equipment(request: Request, account=Depends(require_authenticated_user, scope='function')):
    require_enabled(request, account.db)
    rows = account.db.execute(select(UserEquipment, AssetItem).join(AssetItem, AssetItem.id == UserEquipment.asset_id)
        .where(UserEquipment.user_id == account.user.id, AssetItem.active.is_(True),
               reviewed_source_rights_sql(AssetItem.source_rights))
        .options(undefer(AssetItem.display_name), undefer(AssetItem.effect_key)).order_by(UserEquipment.slot_kind))
    return EquipmentPage(items=[EquippedItem(slot_kind=slot.slot_kind, asset=asset_dto(asset, request, metadata=True))
                                for slot, asset in rows])


@router.get('/vault/opens/by-request', response_model=CaseOpenResult, operation_id='getOpenByRequest', responses=RUNTIME_ERRORS)
def get_open_by_request(request: Request, key: str = Query(min_length=12, max_length=128),
                        account=Depends(require_authenticated_user, scope='function')):
    require_schema(account.db)
    valid_key(key)
    opening = account.db.scalar(select(CaseOpen).where(CaseOpen.user_id == account.user.id,
                                                       CaseOpen.request_key == key))
    if opening is None or opening.decision_trace.get('runtime') != 'free-vault-v1':
        raise AuthError(404, 'NOT_FOUND', 'Opening receipt not found.')
    replay_receipt(account.db, account.user.id, opening)
    return receipt_result(account.db, account.user.id, opening, request, True)

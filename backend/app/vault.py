"""Common-case read views and a two-stage CSPRNG engine; no runtime open/activation."""
from dataclasses import dataclass
from typing import Literal
from uuid import UUID
import secrets

from fastapi import APIRouter, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import func, select

from app.aura import DraftPolicy
from app.auth_schemas import ErrorResponse
from app.blog_schemas import Pagination
from app.inventory import ready_asset
from app.models import AssetItem, CaseDefinition as CaseRow, CaseLootTable, CaseLootRarity, CasePoolItem, RewardPolicyVersion
from app.security import AuthError

router = APIRouter(prefix='/api/v1/vault', tags=['Vault'])
RARITIES = ('D', 'C', 'B', 'A', 'S')
ERRORS = {code: {'model': ErrorResponse} for code in (422,429,500)}


@dataclass(frozen=True)
class DrawPool:
    id: UUID
    policy_id: UUID
    version: int
    minimum: int
    maximum: int | None
    weights: tuple[int, ...]
    buckets: tuple[tuple[tuple[UUID, int], ...], ...]


def weighted(values, randbelow):
    if not values or any(weight < 0 for _, weight in values) or sum(weight for _, weight in values) <= 0:
        raise ValueError('Invalid weighted choices.')
    total = sum(weight for _, weight in values)
    point = randbelow(total)
    if not isinstance(point, int) or not 0 <= point < total:
        raise ValueError('Invalid random draw.')
    cursor = 0
    for value, weight in values:
        cursor += weight
        if point < cursor:
            return value, point
    raise ValueError('Weighted choices are incomplete.')


def draw(pool, *, randbelow=secrets.randbelow):
    if len(pool.weights) != 5 or len(pool.buckets) != 5 or sum(pool.weights) != 10000:
        raise ValueError('Rarity basis points must sum to10000.')
    index, first = weighted(tuple(enumerate(pool.weights)), randbelow)
    asset, second = weighted(pool.buckets[index], randbelow)
    return asset, {'rarity': RARITIES[index], 'rarity_draw': first, 'item_draw': second}


def choose_band(pools, earned_xp):
    matches = [p for p in pools if p.minimum <= earned_xp and (p.maximum is None or earned_xp < p.maximum)]
    if earned_xp < 0 or len(matches) != 1:
        raise ValueError('Earned XP has no unique case band.')
    return matches[0]


def load_version(db, case_id, version, now, status):
    tables = list(db.scalars(select(CaseLootTable).where(CaseLootTable.case_id == case_id,
        CaseLootTable.odds_version == version).order_by(CaseLootTable.min_earned_xp).with_for_update(read=True).execution_options(populate_existing=True)))
    if not tables or tables[0].min_earned_xp != 0 or tables[-1].max_earned_xp is not None:
        raise ValueError('Odds bands must cover0 to infinity.')
    if len({row.policy_id for row in tables}) != 1:
        raise ValueError('One policy is required per odds version.')
    policy = db.scalar(select(RewardPolicyVersion).where(RewardPolicyVersion.id == tables[0].policy_id).with_for_update(read=True))
    if policy is None or policy.status != status or policy.effective_at > now:
        raise ValueError('Effective matching policy is required.')
    DraftPolicy.model_validate(policy.config_json)
    pools = []
    for index, row in enumerate(tables):
        if (row.status != status or row.active_from > now or row.band_no != index + 1
            or (index and tables[index-1].max_earned_xp != row.min_earned_xp)):
            raise ValueError('Odds version has mixed status, future bands, overlaps or gaps.')
        weights = dict(db.execute(select(CaseLootRarity.rarity, CaseLootRarity.weight_bps).where(CaseLootRarity.loot_table_id == row.id)).all())
        if set(weights) != set(RARITIES) or sum(weights.values()) != 10000 or weights['S'] > 1000 or (index == 0 and weights['S'] >= 100):
            raise ValueError('Invalid rarity basis points or common-case S bounds.')
        choices = {rarity: [] for rarity in RARITIES}
        for item, asset in db.execute(select(CasePoolItem, AssetItem).join(AssetItem, AssetItem.id == CasePoolItem.asset_id).where(
                CasePoolItem.loot_table_id == row.id).order_by(CasePoolItem.asset_id).with_for_update(read=True)):
            if not ready_asset(asset) or asset.kind == 'generator' or asset.rarity != item.rarity or item.item_weight <= 0:
                raise ValueError('Pool contains an unavailable or mismatched asset.')
            choices[item.rarity].append((asset.id, item.item_weight))
        if any(weights[rarity] > 0 and not choices[rarity] for rarity in RARITIES):
            raise ValueError('Positive rarity must contain eligible items.')
        pools.append(DrawPool(row.id, row.policy_id, version, row.min_earned_xp, row.max_earned_xp,
            tuple(weights[rarity] for rarity in RARITIES), tuple(tuple(choices[rarity]) for rarity in RARITIES)))
    return pools


class CaseDefinition(BaseModel):
    id: UUID
    slug: str
    label: str
    cost_khi_van: int = Field(ge=0)
    status: Literal['active', 'retired']


class CaseBand(BaseModel):
    min_earned_xp: int = Field(ge=0)
    max_earned_xp: int | None
    odds_version: int = Field(ge=1)
    weights_bps: dict[Literal['D', 'C', 'B', 'A', 'S'], int]


class CaseDetail(BaseModel):
    case: CaseDefinition
    bands: list[CaseBand]


class CasePage(BaseModel):
    items: list[CaseDefinition]
    pagination: Pagination


def available_case(db, now, case_id=None):
    query = select(CaseRow).where(CaseRow.slug == 'common', CaseRow.status == 'active')
    if case_id is not None:
        query = query.where(CaseRow.id == case_id)
    case = db.scalar(query.with_for_update(read=True))
    if case is None:
        return None
    version = db.scalar(select(func.max(CaseLootTable.odds_version)).where(CaseLootTable.case_id == case.id,
        CaseLootTable.status == 'published', CaseLootTable.active_from <= now))
    if version is None:
        return None
    try:
        pools = load_version(db, case.id, version, now, 'published')
    except ValueError:
        return None
    return CaseDetail(case=CaseDefinition.model_validate(case, from_attributes=True), bands=[CaseBand(
        min_earned_xp=p.minimum, max_earned_xp=p.maximum, odds_version=p.version,
        weights_bps=dict(zip(RARITIES, p.weights))) for p in pools])


@router.get('/cases', response_model=CasePage, operation_id='listCases', responses=ERRORS)
def list_cases(request: Request, page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100)):
    with request.app.state.auth_session_factory() as db, db.begin():
        detail = available_case(db, request.app.state.auth.now())
        items = [detail.case] if detail else []
        return CasePage(items=items[(page-1)*page_size:page*page_size],
            pagination=Pagination(page=page, page_size=page_size, total=len(items), total_pages=len(items)))


@router.get('/cases/{case_id}', response_model=CaseDetail, operation_id='getCase', responses=ERRORS | {404: {'model': ErrorResponse}})
def get_case(case_id: UUID, request: Request):
    with request.app.state.auth_session_factory() as db, db.begin():
        detail = available_case(db, request.app.state.auth.now(), case_id)
        if detail is None:
            raise AuthError(404, 'NOT_FOUND', 'Published common case not available.')
        return detail

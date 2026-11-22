from vault_test_rights import synthetic_rights
from collections import Counter

from datetime import datetime, timedelta, timezone

from math import sqrt

import random

from uuid import uuid4

import pytest

from pydantic import ValidationError

def test_v1_policy_rejects_economics_and_changed_odds():
    from app.vault_v1_policy import FreeVaultPolicy
    assert FreeVaultPolicy.model_validate({'type': 'free-vault-v1'}).duplicate_mode == 'quantity'
    for change in ({'max_daily_opens': 100}, {'xp': 1}, {'cost_khi_van': 1},
                   {'weights_bps': [6890, 2000, 1000, 99, 11]}, {'cooldown_seconds': 1}):
        with pytest.raises(ValidationError):
            FreeVaultPolicy.model_validate({'type': 'free-vault-v1'} | change)

@pytest.mark.parametrize('kind', ['avatar', 'background'])
def test_v1_100000_draws_have_exact_rarity_policy_and_uniform_items(kind):
    from app.vault import DrawPool, draw
    from app.vault_v1_policy import WEIGHTS
    assets = [[uuid4(), uuid4()] for _ in WEIGHTS]
    pool = DrawPool(uuid4(), uuid4(), 1, 0, None, WEIGHTS,
                    tuple(tuple((asset, 1) for asset in bucket) for bucket in assets))
    rng = random.Random(20261114 + (kind == 'background'))
    counts, items = Counter(), Counter()
    for _ in range(100_000):
        asset, trace = draw(pool, randbelow=rng.randrange)
        counts[trace['rarity']] += 1
        items[asset] += 1
    for rarity, weight in zip('DCBAS', WEIGHTS):
        p = weight / 10000
        assert abs(counts[rarity] - 100000*p) < 6*sqrt(100000*p*(1-p))
    assert abs(items[assets[0][0]] / counts['D'] - .5) < .015
    samples = Counter(draw(pool, randbelow=lambda n: 9999 if n == 10000 else rng.randrange(n))[0]
                      for _ in range(10000))
    assert abs(samples[assets[4][0]] - 5000) < 300

@pytest.mark.parametrize('point,rarity', [(0,'D'), (6889,'D'), (6890,'C'), (8889,'C'),
                                        (8890,'B'), (9889,'B'), (9890,'A'), (9989,'A'),
                                        (9990,'S'), (9999,'S')])
def test_v1_rarity_boundaries(point, rarity):
    from app.vault import DrawPool, draw
    from app.vault_v1_policy import WEIGHTS
    pool = DrawPool(uuid4(), uuid4(), 1, 0, None, WEIGHTS,
                    tuple(((uuid4(), 1),) for _ in WEIGHTS))
    values = iter((point, 0))
    assert draw(pool, randbelow=lambda n: next(values))[1]['rarity'] == rarity

@pytest.mark.parametrize('count,seconds', [(0,0), (1,2), (9,2), (10,5), (11,2), (20,5)])
def test_cooldown_success_count_boundary(count, seconds):
    from app.vault_v1_policy import next_open_at
    now = datetime(2026, 11, 14, tzinfo=timezone.utc)
    assert next_open_at(now if count else None, count) == (now + timedelta(seconds=seconds) if count else None)

def test_runtime_defaults_off_without_reading_env_file(monkeypatch):
    from app.config import VaultSettings
    monkeypatch.delenv('VAULT_RUNTIME_ENABLED', raising=False)
    assert VaultSettings(_env_file=None).vault_runtime_enabled is False

def test_disabled_gate_never_touches_database():
    from types import SimpleNamespace
    from unittest.mock import Mock
    from app.security import AuthError
    from app.vault_runtime import require_enabled
    db = Mock()
    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace()))
    with pytest.raises(AuthError) as error:
        require_enabled(request, db)
    assert error.value.code == 'NOT_READY'
    db.scalar.assert_not_called()

def test_legacy_orm_selects_do_not_reference_new_deferred_columns():
    from sqlalchemy import select
    from app.models import AssetItem, CaseDefinition, PostReaction, CommentReaction
    for model in (AssetItem, CaseDefinition, PostReaction, CommentReaction):
        sql = str(select(model))
        for column in ('display_name', 'effect_key', 'runtime_kind', 'meme_asset_id'):
            assert column not in sql

def test_v1_asset_guard_checks_kind_names_and_background_renderer():
    from types import SimpleNamespace
    from app.vault_runtime import ready_runtime_asset
    asset = SimpleNamespace(kind='background', active=True, rarity='B', display_name='Biển sâu',
                            effect_key='lucian-352-deep-sea',
                            source_rights=synthetic_rights('a'*64,name_review_status='approved'))
    assert ready_runtime_asset(asset, 'background')
    assert not ready_runtime_asset(asset, 'avatar')
    asset.effect_key = 'lucian-352'
    assert not ready_runtime_asset(asset, 'background')
    asset.effect_key = 'lucian-352-deep-sea'
    asset.source_rights['name_review_status'] = 'pending'
    assert not ready_runtime_asset(asset, 'background')


def test_cooldown_details_are_allowlisted_and_old_errors_keep_their_shape():
    import json
    from app.main import error_response
    due = '2026-11-15T00:00:02Z'
    response = error_response(429, 'COOLDOWN', 'Please wait.', 2, {'next_open_at': due, 'private_key': 'never expose'})
    error = json.loads(response.body)['error']
    assert response.headers['Retry-After'] == '2'
    assert error['details'] == {'next_open_at': due}
    assert 'never expose' not in response.body.decode()
    assert set(json.loads(error_response(403, 'FORBIDDEN', 'Denied.').body)['error']) == {'code', 'message', 'request_id'}


@pytest.mark.parametrize('revisions,expected', [(['0014_premium_sandbox'], True), (['0013_notifications'], True), (['0012_aura_v1'], True), (['0011_vault_v1'], False), (['0012_aura_v1', '0011_vault_v1'], False), ([], False)])
def test_runtime_requires_single_reviewed_current_schema(revisions, expected):
    from unittest.mock import Mock
    from app.vault_runtime import schema_ready
    db = Mock()
    db.scalars.return_value = revisions
    assert schema_ready(db) is expected


def test_approval_flag_without_provenance_never_makes_an_asset_ready():
    from types import SimpleNamespace
    from app.inventory import ready_asset, asset_dto
    asset = SimpleNamespace(id=uuid4(), slug='unverified', kind='avatar', rarity='D', active=True,
        source_rights={'review_status':'approved'})
    assert not ready_asset(asset)
    request = SimpleNamespace(url_for=lambda *args, **kwargs: 'https://testserver/should-not-be-exposed')
    dto = asset_dto(asset, request)
    assert dto.available is False and dto.media_url is None


def test_catalog_search_rejects_nul_before_building_a_query(monkeypatch):
    from types import SimpleNamespace
    from unittest.mock import Mock
    from app import vault_runtime
    from app.security import AuthError
    monkeypatch.setattr(vault_runtime, 'require_enabled', lambda *args: None)
    db=Mock()
    account=SimpleNamespace(db=db,user=SimpleNamespace(id=uuid4()))
    with pytest.raises(AuthError) as error:
        vault_runtime.catalog(SimpleNamespace(),kind=None,rarity=None,q='bad\x00query',page=1,page_size=20,account=account)
    assert error.value.status==422
    db.execute.assert_not_called()

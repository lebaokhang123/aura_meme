"""Synthetic probability fixtures; no approved prices, odds or released assets."""
from collections import Counter
from math import sqrt
import random
from uuid import uuid4
import pytest
from test_auth import auth,migrated


def test_weighted_draw_boundaries_do_not_select_zero_weight_buckets():
    from app.vault import DrawPool,draw
    asset=uuid4()
    pool=DrawPool(uuid4(),uuid4(),1,0,None,(10000,0,0,0,0),(((asset,1),),(),(),(),()))
    for point in (0,9999):
        values=iter([point,0]);result,trace=draw(pool,randbelow=lambda n:next(values))
        assert result==asset and trace['rarity']=='D'


def test_seeded_100000_simulations_match_both_weighted_stages():
    from app.vault import DrawPool,draw
    ids=[uuid4() for _ in range(6)]
    pool=DrawPool(uuid4(),uuid4(),1,0,None,(6000,2500,1000,450,50),(((ids[0],1),(ids[1],3)),*((((asset,1),) for asset in ids[2:]))))
    rng=random.Random(20261106);counts=Counter();items=Counter()
    for _ in range(100_000):
        asset,trace=draw(pool,randbelow=rng.randrange);counts[trace['rarity']]+=1;items[asset]+=1
    for rarity,weight in zip('DCBAS',pool.weights):
        p=weight/10000
        assert abs(counts[rarity]-100_000*p) < max(10,6*sqrt(100_000*p*(1-p)))
    assert abs(items[ids[0]]/counts['D']-.25)<.015
    print('Synthetic100k counts:',dict(counts),'D first-item ratio:',items[ids[0]]/counts['D'])


def test_band_uses_only_earned_xp_half_open_boundaries():
    from app.vault import DrawPool,choose_band
    p=DrawPool(uuid4(),uuid4(),1,0,100,(10000,0,0,0,0),())
    q=DrawPool(uuid4(),p.policy_id,1,100,None,p.weights,())
    assert choose_band([p,q],99)==p and choose_band([p,q],100)==q
    with pytest.raises(ValueError):choose_band([p,q],-1)


@pytest.fixture
def vault(auth):
    import json
    from uuid import UUID
    from sqlalchemy import text
    from test_auth import register,login
    client,c=auth;owner=UUID(register(client).json()['id']);assert login(client).status_code==200
    case,policy,pools,assets=seed_vault(c,owner,client.app.state.auth.now())
    return client,c,owner,case,policy,pools,assets


def seed_vault(c,owner,now):
    import json
    from sqlalchemy import text
    case,policy=uuid4(),uuid4();pools=[uuid4(),uuid4()];assets=[uuid4() for _ in range(5)]
    config={'xp':{'post':7},'daily_cap':20,'levels':[0,10,1000]}
    c.execute(text("INSERT INTO reward_policy_versions VALUES (:id,1,CAST(:config AS jsonb),'draft',:now,:owner,:now)"),{'id':policy,'config':json.dumps(config),'owner':owner,'now':now})
    c.execute(text("INSERT INTO case_definitions VALUES (:id,'common','Synthetic case',3,'draft',:now,:now)"),{'id':case,'now':now})
    for rarity,asset in zip('DCBAS',assets):
        digest=asset.hex*2;rights={'source':'synthetic fixture','author':'test','license':'CC0-1.0','attribution':'not released','review_status':'approved','sha256':digest,'mime':'image/png'}
        c.execute(text("INSERT INTO asset_items VALUES (:id,:slug,'icon','fixture',:rarity,:key,CAST(:rights AS jsonb),true,:now,:now)"),{'id':asset,'slug':'fixture-'+asset.hex,'rarity':rarity,'key':'catalog/'+digest+'.png','rights':json.dumps(rights),'now':now})
    for index,pool in enumerate(pools):
        c.execute(text("INSERT INTO case_loot_tables VALUES (:id,:case,1,:band,:min,:max,:policy,'draft',:now,:now)"),{'id':pool,'case':case,'band':index+1,'min':0 if index==0 else 100,'max':100 if index==0 else None,'policy':policy,'now':now})
        for rarity,weight,asset in zip('DCBAS',[6000,2500,1000,450,50],assets):
            c.execute(text('INSERT INTO case_loot_rarities VALUES (:pool,:rarity,:weight)'),{'pool':pool,'rarity':rarity,'weight':weight})
            c.execute(text('INSERT INTO case_pool_items VALUES (:pool,:asset,:rarity,1)'),{'pool':pool,'asset':asset,'rarity':rarity})
    return case,policy,pools,assets


@pytest.mark.integration
def test_validate_complete_draft_then_read_published_case_with_exact_contract(vault):
    from sqlalchemy import text
    from sqlalchemy.orm import Session
    from app.vault import load_version
    client,c,_,case,policy,pools,assets=vault
    with Session(bind=c,join_transaction_mode='create_savepoint') as db:
        result=load_version(db,case,1,client.app.state.auth.now(),'draft');assert len(result)==2
    assert client.get('/api/v1/vault/cases').json()['items']==[]
    assert client.get('/api/v1/vault/cases/'+str(case)).status_code==404
    c.execute(text("UPDATE reward_policy_versions SET status='published' WHERE id=:id"),{'id':policy})
    c.execute(text("UPDATE case_loot_tables SET status='published' WHERE case_id=:id"),{'id':case})
    c.execute(text("UPDATE case_definitions SET status='active' WHERE id=:id"),{'id':case})
    body=client.get('/api/v1/vault/cases').json();assert len(body['items'])==1
    assert set(body['items'][0])=={'id','slug','label','cost_khi_van','status'}
    detail=client.get('/api/v1/vault/cases/'+str(case));assert detail.status_code==200
    assert len(detail.json()['bands'])==2 and detail.json()['bands'][0]['weights_bps']['S']==50
    assert all(str(asset) not in detail.text for asset in assets)
    assert client.get('/api/v1/vault/cases?page=999999999999999999999').json()['items']==[]


@pytest.mark.integration
@pytest.mark.parametrize('change',[
 "UPDATE case_loot_rarities SET weight_bps=1 WHERE rarity='D'",
 "DELETE FROM case_loot_rarities WHERE rarity='S'",  # FK means fail before validation if referenced.
 "DELETE FROM case_pool_items WHERE rarity='S'",
 "UPDATE asset_items SET active=false",
 "UPDATE case_loot_tables SET min_earned_xp=101 WHERE band_no=2",
 "UPDATE case_loot_tables SET min_earned_xp=99 WHERE band_no=2",
 "UPDATE case_loot_tables SET max_earned_xp=1000 WHERE band_no=2",
 "UPDATE case_loot_tables SET active_from=active_from+interval '1 day' WHERE band_no=2",
 "UPDATE case_loot_rarities SET weight_bps=CASE WHEN rarity='S' THEN 100 WHEN rarity='D' THEN 5950 ELSE weight_bps END",
])
def test_invalid_version_is_rejected_without_publishing(vault,change):
    from sqlalchemy import text
    from sqlalchemy.orm import Session
    from sqlalchemy.exc import IntegrityError
    from app.vault import load_version
    client,c,_,case,_,_,_=vault
    if change.startswith('DELETE FROM case_loot_rarities'):
        with pytest.raises(IntegrityError),c.begin_nested():c.execute(text(change))
        return
    c.execute(text(change))
    with Session(bind=c,join_transaction_mode='create_savepoint') as db:
        with pytest.raises(ValueError):load_version(db,case,1,client.app.state.auth.now(),'draft')
    assert client.get('/api/v1/vault/cases').json()['items']==[]


@pytest.mark.integration
def test_published_pool_children_and_retired_history_are_immutable(vault):
    from sqlalchemy import text
    from sqlalchemy.exc import IntegrityError
    _,c,_,case,_,pools,_=vault
    c.execute(text("UPDATE case_loot_tables SET status='published' WHERE case_id=:id"),{'id':case})
    for statement in ["UPDATE case_pool_items SET item_weight=2", "DELETE FROM case_pool_items", "UPDATE case_loot_rarities SET weight_bps=1", "UPDATE case_loot_tables SET odds_version=2", "TRUNCATE case_loot_tables CASCADE"]:
        with pytest.raises(IntegrityError),c.begin_nested():c.execute(text(statement))
    c.execute(text("UPDATE case_loot_tables SET status='retired' WHERE case_id=:id"),{'id':case})
    with pytest.raises(IntegrityError),c.begin_nested():c.execute(text("UPDATE case_loot_tables SET status='draft'"))


@pytest.mark.parametrize('weights',[(0,0,0,0,0),(9999,0,0,0,0),(-1,10001,0,0,0)])
def test_bad_weight_totals_or_negative_weights_cannot_draw(weights):
    from app.vault import DrawPool,draw
    p=DrawPool(uuid4(),uuid4(),1,0,None,weights,tuple(((uuid4(),1),) for _ in range(5)))
    with pytest.raises(ValueError):draw(p)


@pytest.mark.integration
@pytest.mark.parametrize('statement',[
    "UPDATE case_definitions SET cost_khi_van=-1",
    "UPDATE case_loot_tables SET odds_version=0",
    "UPDATE case_loot_rarities SET weight_bps=-1",
    "UPDATE case_pool_items SET item_weight=0",
    "UPDATE case_pool_items SET rarity='C' WHERE rarity='D'",
])
def test_case_database_constraints_and_composite_rarity_binding(vault,statement):
    from sqlalchemy import text
    from sqlalchemy.exc import IntegrityError
    _,c,_,_,_,_,_=vault
    with pytest.raises(IntegrityError),c.begin_nested():c.execute(text(statement))


def test_runtime_rng_default_is_python_secrets():
    import inspect,secrets
    from app.vault import draw
    assert inspect.signature(draw).parameters['randbelow'].default is secrets.randbelow

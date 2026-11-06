"""Atomic open/weekly mechanics are draft fixtures only; runtime must remain OFF."""
from datetime import datetime,timedelta,timezone
import json
from uuid import uuid4
import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session
from test_auth import auth,migrated,csrf
from test_blog import mutation
from test_vault import vault

START=datetime(2026,11,9,tzinfo=timezone.utc)


@pytest.fixture
def economy(vault):
    client,c,owner,case,policy,pools,assets=vault
    config=c.scalar(text('SELECT config_json FROM reward_policy_versions WHERE id=:id'),{'id':policy})
    config.update(checkin={'xp_by_weekday':[2]*7,'khi_by_weekday':[10]*7,'weekly_asset_id':str(assets[0])},
                  vault={'daily_free':True,'max_daily_opens':2,'duplicate_mode':'quantity'})
    c.execute(text('UPDATE reward_policy_versions SET config_json=CAST(:config AS jsonb) WHERE id=:id'),{'id':policy,'config':json.dumps(config)})
    with Session(bind=c,join_transaction_mode='create_savepoint') as db:
        yield client,db,owner,case,policy,pools,assets


@pytest.mark.integration
def test_free_paid_and_retry_do_not_double_debit_grant_or_draw(economy):
    from app.checkin import simulate_checkin
    from app.vault_open import simulate_open
    _,db,owner,case,policy,_,assets=economy
    simulate_checkin(db,policy,owner,START)
    first=simulate_open(db,owner,case,'fixture-open-001',START+timedelta(minutes=1),randbelow=lambda n:0)
    def never(n):raise AssertionError('Retry must not draw again')
    retry=simulate_open(db,owner,case,'fixture-open-001',START+timedelta(minutes=2),randbelow=never)
    assert first.open_id==retry.open_id and first.reward_asset_id==retry.reward_asset_id==assets[0]
    assert first.cost_khi_van==0 and retry.already_processed is True
    paid=simulate_open(db,owner,case,'fixture-open-002',START+timedelta(minutes=3),randbelow=lambda n:0)
    assert paid.cost_khi_van==3 and paid.khi_van_balance==7
    assert db.scalar(text('SELECT sum(quantity) FROM user_inventory'))==2
    assert db.scalar(text('SELECT count(*) FROM inventory_grants'))==2
    assert db.scalar(text('SELECT count(*) FROM case_opens'))==2
    assert db.scalar(text("SELECT count(*) FROM wallet_transactions WHERE reason='case_open'"))==1
    with pytest.raises(ValueError,match='quota'):simulate_open(db,owner,case,'fixture-open-003',START+timedelta(minutes=4))


@pytest.mark.integration
@pytest.mark.parametrize('days',[7,30,90])
def test_synthetic_economy_and_weekly_grants_preserve_all_caches(economy,days):
    from app.checkin import simulate_checkin
    from app.vault_open import simulate_open
    _,db,owner,case,policy,_,_=economy
    for day in range(days):
        now=START+timedelta(days=day)
        simulate_checkin(db,policy,owner,now)
        for turn in range(2):simulate_open(db,owner,case,f'fixture-{day:03d}-{turn}-open',now+timedelta(minutes=turn+1),randbelow=lambda n:0)
    assert db.scalar(text('SELECT khi_van_balance FROM wallets'))==days*7
    assert db.scalar(text('SELECT sum(delta_khi_van) FROM wallet_transactions'))==days*7
    assert db.scalar(text('SELECT sum(quantity) FROM user_inventory'))==days*2+days//7
    assert db.scalar(text('SELECT sum(quantity) FROM inventory_grants'))==days*2+days//7
    assert db.scalar(text("SELECT count(*) FROM inventory_grants WHERE source_type='weekly_streak'"))==days//7
    assert db.scalar(text('SELECT count(*) FROM case_opens'))==days*2


@pytest.mark.integration
def test_weekly_7of7_once_at_sunday_0700_not_streak_only(economy):
    from app.checkin import simulate_checkin
    _,db,owner,_,policy,_,_=economy
    for day in range(6):simulate_checkin(db,policy,owner,START+timedelta(days=day))
    simulate_checkin(db,policy,owner,START+timedelta(days=6)-timedelta(minutes=1))
    assert db.scalar(text('SELECT count(*) FROM inventory_grants'))==0
    at_sunday=START+timedelta(days=6)
    simulate_checkin(db,policy,owner,at_sunday);simulate_checkin(db,policy,owner,at_sunday+timedelta(seconds=1))
    assert db.scalar(text('SELECT count(*) FROM inventory_grants'))==1
    assert db.scalar(text('SELECT event_key FROM inventory_grants'))=='weekly:2026-11-09'


@pytest.mark.integration
def test_missing_one_effective_day_does_not_grant_weekly_icon(economy):
    from app.checkin import simulate_checkin
    _,db,owner,_,policy,_,_=economy
    for day in [0,1,3,4,5,6]:simulate_checkin(db,policy,owner,START+timedelta(days=day))
    assert db.scalar(text('SELECT count(*) FROM inventory_grants'))==0


@pytest.mark.integration
@pytest.mark.parametrize('table',['wallet_transactions','case_opens','inventory_grants'])
def test_insert_failure_rolls_back_debit_receipt_inventory_and_grant(economy,table):
    from app.checkin import simulate_checkin
    from app.vault_open import simulate_open
    from sqlalchemy.exc import DBAPIError
    _,db,owner,case,policy,_,_=economy
    simulate_checkin(db,policy,owner,START)
    simulate_open(db,owner,case,'fixture-free-000',START+timedelta(minutes=1),randbelow=lambda n:0)
    db.execute(text("CREATE FUNCTION opening_fail() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'synthetic failure'; END $$"))
    db.execute(text(f'CREATE TRIGGER opening_fail BEFORE INSERT ON {table} FOR EACH ROW EXECUTE FUNCTION opening_fail()'))
    with pytest.raises(DBAPIError):simulate_open(db,owner,case,'fixture-paid-001',START+timedelta(minutes=2),randbelow=lambda n:0)
    assert db.scalar(text('SELECT khi_van_balance FROM wallets'))==10
    assert db.scalar(text('SELECT sum(quantity) FROM user_inventory'))==1
    assert db.scalar(text('SELECT count(*) FROM case_opens'))==1
    assert db.scalar(text('SELECT count(*) FROM inventory_grants'))==1
    assert db.scalar(text("SELECT count(*) FROM wallet_transactions WHERE reason='case_open'"))==0


@pytest.mark.integration
def test_runtime_open_checks_auth_csrf_origin_then503_without_writes(economy):
    client,db,_,case,policy,_,_=economy;path=f'/api/v1/vault/cases/{case}/open'
    db.execute(text("UPDATE reward_policy_versions SET status='published' WHERE id=:id"),{'id':policy})
    db.execute(text("UPDATE case_loot_tables SET status='published' WHERE case_id=:id"),{'id':case})
    db.execute(text("UPDATE case_definitions SET status='active' WHERE id=:id"),{'id':case})
    headers={'Origin':'https://testserver','X-CSRF-Token':csrf(client),'Idempotency-Key':'fixture-http-000'}
    assert client.post(path,headers=headers,json={'reward_asset_id':str(uuid4()),'cost_khi_van':0}).status_code==503
    assert client.post(path,headers=headers).json()['error']['code']=='NOT_READY'
    for key in ['short',' '*12,'x'*129]:assert client.post(path,headers=headers|{'Idempotency-Key':key}).status_code==422
    assert client.post(path,headers={'Idempotency-Key':'fixture-http-000'}).status_code==403
    assert client.post(path,headers=headers|{'Origin':'https://evil.test'}).status_code==403
    client.cookies.clear();assert client.post(path,headers=headers).status_code==401
    for table in ['case_opens','wallet_transactions','wallets','inventory_grants','user_inventory']:
        assert db.scalar(text('SELECT count(*) FROM '+table))==0


@pytest.mark.integration
def test_same_key_timestamp_reordering_replays_original_receipt(economy):
    from app.checkin import simulate_checkin
    from app.vault_open import simulate_open
    _,db,owner,case,policy,_,_=economy
    simulate_checkin(db,policy,owner,START)
    simulate_open(db,owner,case,'fixture-first-free',START+timedelta(minutes=1))
    now=START+timedelta(minutes=2)
    first=simulate_open(db,owner,case,'fixture-paid-same',now+timedelta(milliseconds=1))
    again=simulate_open(db,owner,case,'fixture-paid-same',now)
    assert first.open_id==again.open_id and again.already_processed


@pytest.mark.integration
def test_inventory_cache_corruption_blocks_receipt_replay_without_repair(economy):
    from app.checkin import simulate_checkin
    from app.vault_open import simulate_open
    _,db,owner,case,policy,_,_=economy
    simulate_checkin(db,policy,owner,START)
    simulate_open(db,owner,case,'fixture-first-free',START+timedelta(minutes=1))
    db.execute(text('UPDATE user_inventory SET quantity=99'))
    with pytest.raises(ValueError,match='[Ii]nventory'):simulate_open(db,owner,case,'fixture-first-free',START+timedelta(minutes=2))
    assert db.scalar(text('SELECT quantity FROM user_inventory'))==99
    assert db.scalar(text('SELECT count(*) FROM case_opens'))==1


@pytest.mark.integration
def test_band_ignores_bonus_and_cached_level_and_uses_signed_base(economy):
    from app.checkin import simulate_checkin
    from app.vault_open import simulate_open
    from app.models import AuraLedger
    _,db,owner,case,policy,pools,_=economy
    simulate_checkin(db,policy,owner,START)
    db.add(AuraLedger(id=uuid4(),user_id=owner,event_key='synthetic-vip-fixture',event_type='post',
        source_actor_id=owner,source_post_id=None,source_comment_id=None,policy_id=policy,base_xp=40,bonus_xp=80,
        tier_at_event='PRIME',multiplier_at_event=3,reverses_id=None,occurred_at=START))
    db.flush()
    db.execute(text('UPDATE user_progress SET aura_xp_earned=42,aura_xp_bonus=80,fair_level_cached=999'))
    simulate_open(db,owner,case,'fixture-fairness-key',START+timedelta(minutes=1))
    assert db.scalar(text('SELECT loot_table_id FROM case_opens'))==pools[0]
    assert db.scalar(text('SELECT earned_xp_at_open FROM case_opens'))==42


@pytest.mark.integration
def test_insufficient_balance_does_not_initialize_or_mint_anything(economy):
    from app.vault_open import simulate_open
    _,db,owner,case,policy,_,_=economy
    db.execute(text("UPDATE reward_policy_versions SET config_json=jsonb_set(config_json,'{vault,daily_free}','false') WHERE id=:id"),{'id':policy})
    with pytest.raises(ValueError,match='balance'):simulate_open(db,owner,case,'fixture-insufficient',START)
    for table in ['wallets','wallet_transactions','case_opens','user_inventory','inventory_grants']:
        assert db.scalar(text('SELECT count(*) FROM '+table))==0


@pytest.mark.integration
def test_same_key_different_case_conflicts_without_new_grant(economy):
    from app.vault_open import simulate_open
    _,db,owner,case,_,_,_=economy
    simulate_open(db,owner,case,'fixture-bound-case',START)
    with pytest.raises(ValueError,match='conflicts'):simulate_open(db,owner,uuid4(),'fixture-bound-case',START)
    assert db.scalar(text('SELECT count(*) FROM inventory_grants'))==1


@pytest.mark.integration
def test_weekly_unavailable_asset_rolls_back_seventh_claim(economy):
    from app.checkin import simulate_checkin
    _,db,owner,_,policy,_,assets=economy
    for day in range(6):simulate_checkin(db,policy,owner,START+timedelta(days=day))
    db.execute(text('UPDATE asset_items SET active=false WHERE id=:id'),{'id':assets[0]})
    with pytest.raises(ValueError,match='approved'):simulate_checkin(db,policy,owner,START+timedelta(days=6))
    assert db.scalar(text('SELECT count(*) FROM daily_checkins'))==6
    assert db.scalar(text('SELECT khi_van_balance FROM wallets'))==60
    assert db.scalar(text('SELECT aura_xp_earned FROM user_progress'))==12
    assert db.scalar(text('SELECT count(*) FROM inventory_grants'))==0


@pytest.mark.integration
def test_daily_free_unique_and_append_only_histories_are_enforced_by_postgres(economy):
    from app.vault_open import simulate_open
    from app.models import CaseOpen
    from sqlalchemy import select
    from sqlalchemy.exc import IntegrityError
    _,db,owner,case,_,_,_=economy
    simulate_open(db,owner,case,'fixture-one-free',START)
    row=dict(db.execute(select(CaseOpen.__table__)).mappings().one());row.update(id=uuid4(),request_key='fixture-another-free')
    with pytest.raises(IntegrityError) as error,db.begin_nested():db.execute(CaseOpen.__table__.insert().values(**row))
    assert error.value.orig.diag.constraint_name=='uq_case_opens_daily_free'
    for statement in ['UPDATE case_opens SET cost_khi_van=0','DELETE FROM case_opens','TRUNCATE case_opens CASCADE','UPDATE inventory_grants SET quantity=2','DELETE FROM inventory_grants','TRUNCATE inventory_grants CASCADE']:
        with pytest.raises(IntegrityError),db.begin_nested():db.execute(text(statement))
    assert db.scalar(text('SELECT count(*) FROM case_opens'))==1


@pytest.mark.integration
@pytest.mark.parametrize('wrong',['quantity','asset','owner','policy'])
def test_case_grant_binding_rejects_forged_result_before_fk_or_unique(economy,wrong):
    from app.vault_open import simulate_open
    from app.models import CaseOpen,InventoryGrant
    from sqlalchemy import select
    from sqlalchemy.exc import IntegrityError
    _,db,owner,case,policy,_,assets=economy
    simulate_open(db,owner,case,'fixture-one-free',START,randbelow=lambda n:0)
    row=dict(db.execute(select(CaseOpen.__table__)).mappings().one())
    opening=uuid4();row.update(id=opening,request_key='fixture-unbound-free',effective_day=(START+timedelta(days=1)).date(),created_at=START+timedelta(days=1))
    db.execute(CaseOpen.__table__.insert().values(**row))
    grant=dict(id=uuid4(),user_id=owner,asset_id=assets[0],event_key='case:'+str(opening),quantity=1,source_type='case_open',case_open_id=opening,policy_id=policy,granted_at=row['created_at'])
    grant[{'quantity':'quantity','asset':'asset_id','owner':'user_id','policy':'policy_id'}[wrong]]=2 if wrong=='quantity' else assets[1] if wrong=='asset' else uuid4()
    with pytest.raises(IntegrityError,match='Case grant') as error,db.begin_nested():db.execute(InventoryGrant.__table__.insert().values(**grant))
    assert error.value.orig.sqlstate=='23514'

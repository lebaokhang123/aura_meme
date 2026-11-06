"""Independent PostgreSQL transactions: retry, quota, balance and COMMIT rollback."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime,timedelta,timezone
from threading import Event
from uuid import UUID
import json
import pytest
from sqlalchemy import event,text
from sqlalchemy.orm import Session
from sqlalchemy.exc import DBAPIError
from app.checkin import simulate_checkin
from app.vault_open import simulate_open
from test_auth import migrated
from test_comments_concurrency import race_comments,wait_for_lock
from test_vault import seed_vault


@pytest.fixture
def opening_race(race_comments):
    client,_,engine,_,tag=race_comments;owner=UUID(client.get('/api/v1/users/me').json()['id']);now=datetime.now(timezone.utc)
    with engine.begin() as c:
        case,policy,pools,assets=seed_vault(c,owner,now)
        config={'xp':{'post':7},'daily_cap':20,'levels':[0,10],
            'checkin':{'xp_by_weekday':[2]*7,'khi_by_weekday':[3]*7},
            'vault':{'daily_free':True,'max_daily_opens':2,'duplicate_mode':'quantity'}}
        c.execute(text('UPDATE reward_policy_versions SET config_json=CAST(:config AS jsonb) WHERE id=:id'),{'id':policy,'config':json.dumps(config)})
    with Session(engine) as db,db.begin():simulate_checkin(db,policy,owner,now)
    try:yield owner,case,policy,pools,assets,now,engine,tag
    finally:
        with engine.begin() as c:
            args={'owner':owner,'case':case,'policy':policy,'assets':assets,'pools':pools}
            assert c.scalar(text('SELECT count(*) FROM case_opens WHERE user_id=:owner AND case_id<>:case'),args)==0
            assert c.scalar(text('SELECT count(*) FROM inventory_grants WHERE user_id=:owner AND (policy_id<>:policy OR NOT(asset_id=ANY(:assets)))'),args)==0
            assert c.scalar(text('SELECT count(*) FROM user_inventory WHERE user_id=:owner AND NOT(asset_id=ANY(:assets))'),args)==0
            assert c.scalar(text('SELECT count(*) FROM wallet_transactions WHERE user_id=:owner AND policy_id<>:policy'),args)==0
            assert c.scalar(text('SELECT count(*) FROM aura_ledger WHERE user_id=:owner AND policy_id<>:policy'),args)==0
            for table in ['inventory_grants','case_opens','daily_checkins','wallet_transactions','aura_ledger']:
                c.exec_driver_sql('ALTER TABLE '+table+' DISABLE TRIGGER '+table+'_immutable')
                c.execute(text('DELETE FROM '+table+' WHERE user_id=:owner'),args)
                c.exec_driver_sql('ALTER TABLE '+table+' ENABLE TRIGGER '+table+'_immutable')
            for table in ['user_inventory','wallets','user_progress']:c.execute(text('DELETE FROM '+table+' WHERE user_id=:owner'),args)
            c.execute(text('DELETE FROM case_pool_items WHERE loot_table_id=ANY(:pools)'),args)
            c.execute(text('DELETE FROM case_loot_rarities WHERE loot_table_id=ANY(:pools)'),args)
            c.execute(text('DELETE FROM case_loot_tables WHERE id=ANY(:pools)'),args)
            c.execute(text('DELETE FROM case_definitions WHERE id=:case'),args)
            c.execute(text('DELETE FROM asset_items WHERE id=ANY(:assets)'),args)
            c.execute(text('DELETE FROM reward_policy_versions WHERE id=:policy'),args)


@pytest.mark.integration
@pytest.mark.parametrize('mode',['same-key','quota','balance'])
def test_racing_opens_never_duplicate_debit_or_exceed_quota_or_balance(opening_race,mode):
    owner,case,policy,_,_,now,engine,tag=opening_race
    if mode!='balance':
        with Session(engine) as db,db.begin():simulate_open(db,owner,case,'fixture-before-free',now+timedelta(minutes=1))
    else:
        with engine.begin() as c:c.execute(text("UPDATE reward_policy_versions SET config_json=jsonb_set(config_json,'{vault,daily_free}','false') WHERE id=:id"),{'id':policy})
    locked,release=Event(),Event()
    def pause(conn,cursor,statement,parameters,context,executemany):
        if 'FROM users' in statement and 'FOR UPDATE' in statement and not locked.is_set():locked.set();assert release.wait(7)
    def run(key):
        try:
            with Session(engine) as db,db.begin():return simulate_open(db,owner,case,key,now+timedelta(minutes=2),randbelow=lambda n:0)
        except ValueError as error:return str(error)
    event.listen(engine,'after_cursor_execute',pause)
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            first=pool.submit(run,'fixture-racing-key-1')
            try:
                assert locked.wait(5)
                second=pool.submit(run,'fixture-racing-key-1' if mode=='same-key' else 'fixture-racing-key-2')
                wait_for_lock(engine,tag)
            finally:release.set()
            results=[first.result(timeout=15),second.result(timeout=15)]
        if mode=='same-key':assert sorted(x.already_processed for x in results)==[False,True]
        else:
            errors=[x for x in results if isinstance(x,str)];assert len(errors)==1
            assert ('quota' if mode=='quota' else 'balance') in errors[0]
        with engine.connect() as c:
            assert c.scalar(text('SELECT khi_van_balance FROM wallets WHERE user_id=:id'),{'id':owner})==0
            assert c.scalar(text("SELECT count(*) FROM wallet_transactions WHERE user_id=:id AND reason='case_open'"),{'id':owner})==1
            assert c.scalar(text('SELECT count(*) FROM case_opens WHERE user_id=:id'),{'id':owner})==(1 if mode=='balance' else 2)
            assert c.scalar(text('SELECT sum(quantity) FROM inventory_grants WHERE user_id=:id'),{'id':owner})==(1 if mode=='balance' else 2)
    finally:release.set();event.remove(engine,'after_cursor_execute',pause)


@pytest.mark.integration
def test_open_deferred_commit_failure_preserves_credit_and_inventory(opening_race):
    owner,case,_,_,_,now,engine,_=opening_race
    with Session(engine) as db,db.begin():simulate_open(db,owner,case,'fixture-before-free',now+timedelta(minutes=1))
    try:
        with engine.begin() as c:
            c.exec_driver_sql("CREATE FUNCTION open_commit_fail() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'synthetic commit failure'; END $$")
            c.exec_driver_sql('CREATE CONSTRAINT TRIGGER open_commit_fail AFTER INSERT ON case_opens DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION open_commit_fail()')
        with pytest.raises(DBAPIError):
            with Session(engine) as db,db.begin():simulate_open(db,owner,case,'fixture-commit-fail',now+timedelta(minutes=2))
        with engine.connect() as c:
            assert c.scalar(text('SELECT khi_van_balance FROM wallets WHERE user_id=:id'),{'id':owner})==3
            assert c.scalar(text('SELECT count(*) FROM case_opens WHERE user_id=:id'),{'id':owner})==1
            assert c.scalar(text('SELECT sum(quantity) FROM user_inventory WHERE user_id=:id'),{'id':owner})==1
            assert c.scalar(text("SELECT count(*) FROM wallet_transactions WHERE user_id=:id AND reason='case_open'"),{'id':owner})==0
    finally:
        with engine.begin() as c:
            c.exec_driver_sql('DROP TRIGGER open_commit_fail ON case_opens')
            c.exec_driver_sql('DROP FUNCTION open_commit_fail()')

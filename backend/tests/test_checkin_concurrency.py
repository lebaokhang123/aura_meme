"""Committed independent PostgreSQL claims; temporary hooks and fixtures are cleaned exactly."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime,timezone,timedelta
from threading import Event
from uuid import UUID,uuid4
import json
import pytest
from sqlalchemy import event,text
from sqlalchemy.orm import Session

from app.checkin import simulate_checkin
from test_auth import migrated
from test_comments_concurrency import race_comments,wait_for_lock


@pytest.fixture
def committed_checkin(race_comments):
    client,_,engine,_,tag=race_comments
    owner=UUID(client.get('/api/v1/users/me').json()['id'])
    policy,now=uuid4(),datetime.now(timezone.utc)
    config={'xp':{'post':7},'daily_cap':20,'levels':[0,10],
        'checkin':{'xp_by_weekday':[2]*7,'khi_by_weekday':[1]*7}}
    with engine.begin() as connection:
        connection.execute(text("INSERT INTO reward_policy_versions VALUES (:id,1,CAST(:config AS jsonb),'draft',:now,:owner,:now)"),
            {'id':policy,'owner':owner,'now':now-timedelta(seconds=1),'config':json.dumps(config)})
    try: yield owner,policy,now,engine,tag
    finally:
        with engine.begin() as connection:
            assert connection.scalar(text("SELECT count(*) FROM aura_ledger WHERE user_id=:owner AND (policy_id<>:policy OR event_type<>'checkin')"),{'owner':owner,'policy':policy}) == 0
            assert connection.scalar(text("SELECT count(*) FROM wallet_transactions WHERE user_id=:owner AND (policy_id<>:policy OR reason<>'checkin')"),{'owner':owner,'policy':policy}) == 0
            for table,trigger in [('daily_checkins','daily_checkins_immutable'),('wallet_transactions','wallet_transactions_immutable'),('aura_ledger','aura_ledger_immutable')]:
                connection.exec_driver_sql('ALTER TABLE '+table+' DISABLE TRIGGER '+trigger)
                connection.execute(text('DELETE FROM '+table+' WHERE user_id=:owner'),{'owner':owner})
                connection.exec_driver_sql('ALTER TABLE '+table+' ENABLE TRIGGER '+trigger)
            for table in ['user_progress','wallets']:
                connection.execute(text('DELETE FROM '+table+' WHERE user_id=:owner'),{'owner':owner})
            connection.execute(text('DELETE FROM reward_policy_versions WHERE id=:id'),{'id':policy})


@pytest.mark.integration
def test_two_sessions_claim_one_receipt_and_one_credit(committed_checkin):
    owner,policy,now,engine,tag=committed_checkin
    locked,release=Event(),Event()
    def pause(conn,cursor,statement,parameters,context,executemany):
        if 'FROM users' in statement and 'FOR UPDATE' in statement and not locked.is_set():
            locked.set()
            assert release.wait(7)
    event.listen(engine,'after_cursor_execute',pause)
    def claim():
        with Session(engine) as db,db.begin():
            return simulate_checkin(db,policy,owner,now)
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            first=pool.submit(claim)
            try:
                assert locked.wait(5)
                second=pool.submit(claim)
                wait_for_lock(engine,tag)
            finally: release.set()
            results=[first.result(timeout=15),second.result(timeout=15)]
        assert sorted(result.already_checked_in for result in results) == [False,True]
        assert {result.earned_xp_delta for result in results} == {2}
        with engine.connect() as connection:
            for table in ['daily_checkins','aura_ledger','wallet_transactions']:
                assert connection.scalar(text('SELECT count(*) FROM '+table+' WHERE user_id=:owner'),{'owner':owner}) == 1
            assert connection.scalar(text('SELECT khi_van_balance FROM wallets WHERE user_id=:owner'),{'owner':owner}) == 1
    finally:
        release.set()
        event.remove(engine,'after_cursor_execute',pause)


@pytest.mark.integration
def test_deferred_commit_failure_preserves_all_claim_state(committed_checkin):
    from sqlalchemy.exc import DBAPIError
    owner,policy,now,engine,_=committed_checkin
    try:
        with engine.begin() as connection:
            connection.exec_driver_sql("CREATE FUNCTION m62_commit_fail() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'Synthetic claim commit rejection'; END $$")
            connection.exec_driver_sql('CREATE CONSTRAINT TRIGGER m62_commit_fail AFTER INSERT ON daily_checkins DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION m62_commit_fail()')
        with pytest.raises(DBAPIError):
            with Session(engine) as db,db.begin(): simulate_checkin(db,policy,owner,now)
        with engine.connect() as connection:
            for table in ['daily_checkins','aura_ledger','wallet_transactions','wallets','user_progress']:
                assert connection.scalar(text('SELECT count(*) FROM '+table+' WHERE user_id=:owner'),{'owner':owner}) == 0
    finally:
        with engine.begin() as connection:
            connection.exec_driver_sql('DROP TRIGGER m62_commit_fail ON daily_checkins')
            connection.exec_driver_sql('DROP FUNCTION m62_commit_fail()')

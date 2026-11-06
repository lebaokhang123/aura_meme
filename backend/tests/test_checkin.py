"""Synthetic draft check-ins; no approved economy or production activation."""
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4
import json
import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session
from test_auth import auth, migrated, register, login
from test_blog import mutation


START = datetime(2026,11,9,tzinfo=timezone.utc)


@pytest.fixture
def checkin(auth):
    client, connection = auth
    response=register(client)
    assert response.status_code == 201 and login(client).status_code == 200
    owner, policy = UUID(response.json()['id']), uuid4()
    config={'xp':{'post':7,'reaction':3,'comment':4},'daily_cap':20,'levels':[0,10,1000],
        'checkin':{'xp_by_weekday':[2,3,4,5,6,7,8],'khi_by_weekday':[1,1,1,1,1,1,1]}}
    connection.execute(text("INSERT INTO reward_policy_versions VALUES (:id,1,CAST(:config AS jsonb),'draft',:now,:owner,:now)"),
        {'id':policy,'owner':owner,'now':client.app.state.auth.now(),'config':json.dumps(config)})
    with Session(bind=connection,join_transaction_mode='create_savepoint') as db:
        yield client,db,owner,policy


@pytest.mark.integration
def test_same_effective_day_replays_receipt_without_double_credit(checkin):
    from app.checkin import simulate_checkin
    _,db,owner,policy=checkin
    first=simulate_checkin(db,policy,owner,START)
    again=simulate_checkin(db,policy,owner,START+timedelta(minutes=1))
    assert first.already_checked_in is False and again.already_checked_in is True
    assert first.effective_day == again.effective_day == START.date()
    assert first.earned_xp_delta == again.earned_xp_delta == 2
    assert first.khi_van_delta == again.khi_van_delta == 1
    for table in ['daily_checkins','aura_ledger','wallet_transactions']:
        assert db.scalar(text('SELECT count(*) FROM '+table)) == 1
    assert db.scalar(text('SELECT aura_xp_total FROM user_progress')) == 2
    assert db.scalar(text('SELECT khi_van_balance FROM wallets')) == 1


@pytest.mark.integration
def test_0659_and_0700_vietnam_are_different_effective_days(checkin):
    from app.checkin import simulate_checkin
    _,db,owner,policy=checkin
    previous=simulate_checkin(db,policy,owner,START-timedelta(minutes=1))
    current=simulate_checkin(db,policy,owner,START)
    assert previous.effective_day == (START-timedelta(days=1)).date()
    assert current.effective_day == START.date() and current.streak_days == 2
    assert db.scalar(text('SELECT aura_xp_total FROM user_progress')) == 10
    assert db.scalar(text('SELECT khi_van_balance FROM wallets')) == 2


@pytest.mark.integration
def test_corrupt_streak_is_rejected_without_repair_or_credit(checkin):
    from app.checkin import simulate_checkin
    _,db,owner,policy=checkin
    simulate_checkin(db,policy,owner,START)
    db.execute(text('UPDATE user_progress SET streak_days=99'))
    with pytest.raises(ValueError,match='inconsistent'):
        simulate_checkin(db,policy,owner,START+timedelta(seconds=1))
    assert db.scalar(text('SELECT streak_days FROM user_progress')) == 99
    assert db.scalar(text('SELECT khi_van_balance FROM wallets')) == 1


@pytest.mark.integration
def test_same_day_request_timestamp_reordering_is_still_a_replay(checkin):
    from app.checkin import simulate_checkin
    _,db,owner,policy=checkin
    simulate_checkin(db,policy,owner,START+timedelta(milliseconds=1))
    replay=simulate_checkin(db,policy,owner,START)
    assert replay.already_checked_in is True
    assert db.scalar(text('SELECT count(*) FROM daily_checkins')) == 1


@pytest.mark.parametrize('minutes,offset', [(-1,-1),(0,0),(1,0)])
def test_effective_day_boundary(minutes,offset):
    from app.aura_clock import effective_day
    assert effective_day(START+timedelta(minutes=minutes)) == (START+timedelta(days=offset)).date()


def test_calendar_uses_instant_not_client_timezone_or_dst():
    from zoneinfo import ZoneInfo
    from app.aura_clock import effective_day,week_start
    for zone in ['UTC','Asia/Ho_Chi_Minh','America/New_York','Europe/Berlin']:
        assert effective_day(START.astimezone(ZoneInfo(zone))) == START.date()
        assert week_start(START.astimezone(ZoneInfo(zone))) == START
    with pytest.raises(ValueError): effective_day(START.replace(tzinfo=None))


@pytest.mark.integration
@pytest.mark.parametrize('days',[7,30,90])
def test_draft_daily_simulation_reconciles_ledgers_and_week_eligibility(checkin,days):
    from app.checkin import completed_week,simulate_checkin
    _,db,owner,policy=checkin
    total=0
    for day in range(days):
        result=simulate_checkin(db,policy,owner,START+timedelta(days=day))
        assert result.streak_days == day+1 and result.already_checked_in is False
        total += 2+day%7
    assert db.scalar(text('SELECT SUM(base_xp) FROM aura_ledger')) == total
    assert db.scalar(text('SELECT aura_xp_total FROM user_progress')) == total
    assert db.scalar(text('SELECT SUM(delta_khi_van) FROM wallet_transactions')) == days
    assert db.scalar(text('SELECT khi_van_balance FROM wallets')) == days
    assert completed_week(db,owner,(START+timedelta(days=6)).date()) is True
    assert completed_week(db,owner,(START+timedelta(days=days-1)).date()) == (days%7==0)


@pytest.mark.integration
def test_missing_a_day_resets_only_streak_and_clock_backfill_is_refused(checkin):
    from app.checkin import simulate_checkin
    _,db,owner,policy=checkin
    first=simulate_checkin(db,policy,owner,START)
    third=simulate_checkin(db,policy,owner,START+timedelta(days=2))
    assert third.streak_days == 1
    assert db.scalar(text('SELECT aura_xp_total FROM user_progress')) == first.earned_xp_delta+third.earned_xp_delta
    with pytest.raises(ValueError,match='inconsistent'):
        simulate_checkin(db,policy,owner,START+timedelta(days=1))
    assert db.scalar(text('SELECT count(*) FROM daily_checkins')) == 2


@pytest.mark.integration
@pytest.mark.parametrize('table',['wallets','daily_checkins'])
def test_database_failure_rolls_back_all_claim_writes(checkin,table):
    from app.checkin import simulate_checkin
    from sqlalchemy.exc import IntegrityError
    _,db,owner,policy=checkin
    db.execute(text("CREATE FUNCTION m62_reject() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'Synthetic claim failure' USING ERRCODE='23514'; END $$"))
    db.execute(text('CREATE TRIGGER m62_reject BEFORE INSERT ON '+table+' FOR EACH ROW EXECUTE FUNCTION m62_reject()'))
    with pytest.raises(IntegrityError): simulate_checkin(db,policy,owner,START)
    for name in ['wallets','user_progress','daily_checkins','aura_ledger','wallet_transactions']:
        assert db.scalar(text('SELECT count(*) FROM '+name)) == 0


@pytest.mark.integration
def test_day_constraint_and_receipt_ownership_are_database_enforced(checkin):
    from app.checkin import simulate_checkin
    from sqlalchemy.exc import IntegrityError
    _,db,owner,policy=checkin
    simulate_checkin(db,policy,owner,START)
    row=db.execute(text('SELECT * FROM daily_checkins')).mappings().one()
    with pytest.raises(IntegrityError) as fault,db.begin_nested():
        db.execute(text('INSERT INTO daily_checkins VALUES (:owner,:day,:xp,:money,:now)'),
            {'owner':owner,'day':START.date()+timedelta(days=1),'xp':row['aura_ledger_id'],'money':row['wallet_transaction_id'],'now':START})
    assert fault.value.orig.diag.constraint_name == 'ck_daily_checkins_effective_day'
    with pytest.raises(IntegrityError),db.begin_nested():
        db.execute(text('INSERT INTO wallet_transactions VALUES (:id,:owner,\'bad-sign\',1,\'case_open\',:policy,NULL,:now)'),
            {'id':uuid4(),'owner':owner,'policy':policy,'now':START})


@pytest.mark.integration
@pytest.mark.parametrize('target',['xp','money','reversal'])
def test_foreign_receipt_or_wallet_reversal_owner_is_rejected(checkin,target):
    from app.models import AuraLedger,User,Wallet,WalletTransaction
    from sqlalchemy.exc import IntegrityError
    _,db,owner,policy=checkin
    other=uuid4()
    db.execute(User.__table__.insert().values(id=other,username='checkin_other',email='checkin-other@example.com',
        password_hash='synthetic',status='active',created_at=START,updated_at=START))
    pairs={}
    for identity in [owner,other]:
        xp,money=uuid4(),uuid4()
        db.execute(Wallet.__table__.insert().values(user_id=identity,khi_van_balance=0,updated_at=START))
        db.execute(AuraLedger.__table__.insert().values(id=xp,user_id=identity,event_key='fixture-xp',event_type='checkin',
            policy_id=policy,base_xp=2,bonus_xp=0,tier_at_event='FREE',multiplier_at_event=1,occurred_at=START))
        db.execute(WalletTransaction.__table__.insert().values(id=money,user_id=identity,event_key='fixture-money',
            delta_khi_van=1,reason='checkin',policy_id=policy,created_at=START))
        pairs[identity]=(xp,money)
    with pytest.raises(IntegrityError) as error,db.begin_nested():
        if target == 'reversal':
            db.execute(WalletTransaction.__table__.insert().values(id=uuid4(),user_id=other,event_key='foreign-reverse',
                delta_khi_van=-1,reason='reversal',policy_id=policy,reverses_id=pairs[owner][1],created_at=START))
        else:
            db.execute(text('INSERT INTO daily_checkins VALUES (:owner,:day,:xp,:money,:now)'),{
                'owner':owner,'day':START.date(),'xp':pairs[other if target=='xp' else owner][0],
                'money':pairs[other if target=='money' else owner][1],'now':START})
    assert error.value.orig.diag.constraint_name == {'xp':'fk_daily_checkins_owner_aura',
        'money':'fk_daily_checkins_owner_wallet','reversal':'fk_wallet_transactions_owner_reversal'}[target]


@pytest.mark.integration
@pytest.mark.parametrize('table',['wallet_transactions','daily_checkins'])
def test_checkin_history_rejects_update_delete_and_truncate(checkin,table):
    from app.checkin import simulate_checkin
    from sqlalchemy.exc import IntegrityError
    _,db,owner,policy=checkin
    simulate_checkin(db,policy,owner,START)
    for sql in ['DELETE FROM '+table,'UPDATE '+table+' SET user_id=user_id','TRUNCATE '+table+' CASCADE']:
        with pytest.raises(IntegrityError),db.begin_nested(): db.execute(text(sql))


@pytest.mark.integration
@pytest.mark.parametrize('published',[False,True])
def test_runtime_claim_is_explicitly_off_even_with_a_fixture_policy(checkin,published):
    client,db,*_=checkin
    if published: db.execute(text("UPDATE reward_policy_versions SET status='published'"))
    response=mutation(client,'POST','/aura/check-in',{'user_id':str(uuid4()),'effective_day':'2000-01-01','earned_xp_delta':999999})
    assert response.status_code == 503 and response.json()['error']['code'] == 'NOT_READY'
    for table in ['wallets','user_progress','daily_checkins','aura_ledger','wallet_transactions']:
        assert db.scalar(text('SELECT count(*) FROM '+table)) == 0


@pytest.mark.integration
@pytest.mark.parametrize('problem',['anonymous','csrf','origin','revoked'])
def test_auth_and_csrf_precede_readiness(checkin,problem):
    client,db,*_=checkin
    if problem=='anonymous': client.cookies.clear()
    if problem=='revoked': db.execute(text('UPDATE auth_sessions SET revoked_at=:now'),{'now':client.app.state.auth.now()})
    response=mutation(client,'POST','/aura/check-in',token='bad' if problem=='csrf' else None,
        origin='https://evil.example' if problem=='origin' else 'https://testserver')
    assert response.status_code == (403 if problem in {'csrf','origin'} else 401)


def test_checkin_contract_keeps_existing_fields_and_adds_approved_503():
    from app.main import app
    contract=app.openapi()
    operation=contract['paths']['/api/v1/aura/check-in']['post']
    assert operation['security'] == [{'sessionCookie':[]}]
    assert {'401','403','422','429','500','503'} <= set(operation['responses'])
    assert set(contract['components']['schemas']['CheckInResult']['properties']) == {
        'effective_day','already_checked_in','earned_xp_delta','bonus_xp_delta','khi_van_delta','streak_days'}

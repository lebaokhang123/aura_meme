"""Readiness never fabricates progress; published policies here are rollback-only fixtures."""
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4
import pytest
from sqlalchemy import text
from test_auth import auth, migrated, register, login
from test_blog import blog
from test_aura_ledger import draft


@pytest.mark.integration
def test_progress_auth_precedes_readiness_and_guest_leaderboard_is_public(auth):
    client, _ = auth
    assert client.get('/api/v1/aura/progress').status_code == 401
    response = client.get('/api/v1/leaderboard')
    assert response.status_code == 503 and response.json()['error']['code'] == 'NOT_READY'
    assert register(client).status_code == 201 and login(client).status_code == 200
    response = client.get('/api/v1/aura/progress')
    assert response.status_code == 503 and response.json()['error']['code'] == 'NOT_READY'


@pytest.fixture
def ready(draft):
    from app.aura import simulate_reward
    client, db, owner, post, policy = draft
    now = client.app.state.auth.now()
    db.execute(text('UPDATE users SET created_at=:time'), {'time': now - timedelta(days=60)})
    db.execute(text('UPDATE reward_policy_versions SET effective_at=:time,created_at=:time'), {'time': now - timedelta(days=30)})
    simulate_reward(db, policy, 'post', post, owner, now)
    db.execute(text('INSERT INTO wallets VALUES (:owner,17,:now)'), {'owner': owner, 'now': now})
    db.execute(text("UPDATE reward_policy_versions SET status='published'"))
    return client, db, owner, policy, now


def entry(db, owner, policy, when, base, bonus=0, reverse=None):
    from app.models import AuraLedger
    ident = uuid4()
    db.execute(AuraLedger.__table__.insert().values(id=ident, user_id=owner, event_key='fixture:'+str(ident),
        event_type='reversal' if reverse else 'checkin' if bonus else 'adjustment', source_actor_id=None,
        source_post_id=None, source_comment_id=None, policy_id=policy, base_xp=base, bonus_xp=bonus,
        tier_at_event='PRIME' if bonus else 'FREE', multiplier_at_event=3 if bonus else 1,
        reverses_id=reverse, occurred_at=when))
    return ident


def member(db, policy, now, ident, score=7, status='active'):
    name = 'rank_' + str(ident.int)
    db.execute(text('INSERT INTO users VALUES (:id,:name,:email,\'synthetic\',:status,:now,:now,:deleted)'),
        {'id': ident, 'name': name, 'email': name+'@example.com', 'status': status, 'now': now, 'deleted': now if status=='deleted' else None})
    db.execute(text("INSERT INTO profiles(user_id,display_name,address,phone,updated_at) VALUES (:id,'Synthetic rank','Private address','Private phone',:now)"), {'id': ident, 'now': now})
    entry(db, ident, policy, now, score)


@pytest.mark.integration
def test_progress_uses_actual_private_state_and_total_vs_earned_levels(ready):
    client, db, owner, policy, now = ready
    entry(db, owner, policy, now, 2, bonus=4)
    db.execute(text('UPDATE user_progress SET aura_xp_earned=9,aura_xp_bonus=4'))
    response = client.get('/api/v1/aura/progress?user_id='+str(uuid4()))
    assert response.status_code == 200, response.text
    assert response.json() == {'earned_xp':9,'bonus_xp':4,'total_xp':13,'level':2,'fair_level':1,'streak_days':0,'khi_van_balance':17}
    assert db.scalar(text('SELECT count(*) FROM aura_ledger')) == 2
    assert 'password' not in response.text and 'email' not in response.text
    assert client.get('/api/v1/leaderboard').json()['items'][0]['earned_xp'] == 9


@pytest.mark.integration
@pytest.mark.parametrize('missing', ['wallet','progress','cache'])
def test_missing_or_inconsistent_account_state_is_not_fabricated(ready, missing):
    client, db, *_ = ready
    if missing == 'wallet': db.execute(text('DELETE FROM wallets'))
    elif missing == 'progress': db.execute(text('DELETE FROM user_progress'))
    else: db.execute(text('UPDATE user_progress SET aura_xp_earned=8'))
    response = client.get('/api/v1/aura/progress')
    assert response.status_code == 503 and response.json()['error']['code'] == 'NOT_READY'
    assert 'earned_xp' not in response.json()
    if missing == 'wallet': assert db.scalar(text('SELECT count(*) FROM wallets')) == 0
    if missing == 'cache': assert db.scalar(text('SELECT aura_xp_earned FROM user_progress')) == 8


@pytest.mark.integration
def test_future_ledger_does_not_fabricate_ready_progress(ready):
    client, db, owner, policy, now = ready
    entry(db,owner,policy,now+timedelta(days=1),100)
    db.execute(text('UPDATE user_progress SET aura_xp_earned=107'))
    assert client.get('/api/v1/aura/progress').status_code == 503


@pytest.mark.integration
def test_wallet_balance_and_owner_fk_are_database_constraints(ready):
    from sqlalchemy.exc import IntegrityError
    client, db, *_ = ready
    with pytest.raises(IntegrityError) as error, db.begin_nested():
        db.execute(text('UPDATE wallets SET khi_van_balance=-1'))
    assert error.value.orig.diag.constraint_name == 'ck_wallets_balance_nonnegative'
    with pytest.raises(IntegrityError), db.begin_nested():
        db.execute(text('INSERT INTO wallets VALUES (:id,0,:now)'), {'id':uuid4(),'now':client.app.state.auth.now()})


@pytest.mark.integration
@pytest.mark.parametrize('variant',['draft','retired','future','malformed'])
def test_only_effective_valid_published_policy_can_be_read(draft, variant):
    client, db, *_ = draft
    now = client.app.state.auth.now()
    if variant == 'retired': db.execute(text("UPDATE reward_policy_versions SET status='retired'"))
    if variant == 'future': db.execute(text("UPDATE reward_policy_versions SET status='published',effective_at=:time"), {'time':now+timedelta(days=1)})
    if variant == 'malformed': db.execute(text("UPDATE reward_policy_versions SET status='published',config_json='{}'::jsonb"))
    for path in ['/api/v1/aura/progress','/api/v1/leaderboard']:
        response = client.get(path)
        assert response.status_code == 503 and response.json()['error']['code'] == 'NOT_READY'
        assert 'config_json' not in response.text and 'levels' not in response.text


@pytest.mark.integration
def test_leaderboard_earned_only_stable_global_rank_and_private_whitelist(ready):
    client, db, owner, policy, now = ready
    for ident in [UUID(int=1),UUID(int=2)]: member(db,policy,now,ident)
    member(db,policy,now,UUID(int=3),999,status='locked')
    member(db,policy,now,UUID(int=4),999,status='deleted')
    client.cookies.clear()
    expected = sorted([owner,UUID(int=1),UUID(int=2)])
    for page, ident in enumerate(expected,1):
        response = client.get('/api/v1/leaderboard?page_size=1&page='+str(page))
        assert response.status_code == 200, response.text
        dto = response.json()
        assert dto['pagination']['total'] == 3
        item = dto['items'][0]
        assert item['rank'] == page and item['user']['id'] == str(ident) and item['earned_xp'] == 7
        assert set(item['user']) == {'id','username','display_name','created_at','bio','avatar_url'}
        assert 'Private address' not in response.text and '@example.com' not in response.text
    assert client.get('/api/v1/leaderboard?page='+str(10**80)).json()['items'] == []


@pytest.mark.integration
def test_week_uses_signed_base_delta_and_current_reversal_week(ready):
    from app.aura_reads import week_start
    client, db, owner, policy, now = ready
    start = week_start(now)
    old = entry(db,owner,policy,start-timedelta(seconds=1),10)
    entry(db,owner,policy,start+timedelta(seconds=1),-10,reverse=old)
    assert client.get('/api/v1/leaderboard?period=week').json()['items'] == []
    assert client.get('/api/v1/leaderboard?period=all').json()['items'][0]['earned_xp'] == 7


@pytest.mark.parametrize('minute,expected', [(-1,'2026-10-26T00:00:00+00:00'),(0,'2026-11-02T00:00:00+00:00'),(1,'2026-11-02T00:00:00+00:00')])
def test_week_boundary_monday_0700_vietnam(minute, expected):
    from app.aura_reads import week_start
    now = datetime(2026,11,2,tzinfo=timezone.utc)+timedelta(minutes=minute)
    assert week_start(now).isoformat() == expected


@pytest.mark.integration
@pytest.mark.parametrize('query',['page=0','page_size=101','period=bogus'])
def test_leaderboard_query_validation_is_422(auth, query):
    client, _ = auth
    assert client.get('/api/v1/leaderboard?'+query).status_code == 422


@pytest.mark.integration
@pytest.mark.parametrize('path,expected',[('/api/v1/aura/progress',401),('/api/v1/leaderboard',503)])
def test_new_read_boundaries_require_https_and_keep_rate_limits(auth,path,expected):
    from fastapi.testclient import TestClient
    from app.main import app
    client, _ = auth
    insecure=TestClient(app,base_url='http://testserver')
    try: assert insecure.get(path).status_code == 403
    finally: insecure.close()
    responses=[client.get(path).status_code for _ in range(61)]
    assert responses[:60] == [expected]*60 and responses[-1] == 429


def test_runtime_contract_only_adds_two_read_endpoints_with_503():
    from app.main import app
    contract=app.openapi()
    for path in ['/api/v1/aura/progress','/api/v1/leaderboard']:
        assert set(contract['paths'][path]) == {'get'}
        assert '503' in contract['paths'][path]['get']['responses']
    assert contract['paths']['/api/v1/aura/progress']['get']['security'] == [{'sessionCookie':[]}]
    assert not contract['paths']['/api/v1/leaderboard']['get'].get('security')

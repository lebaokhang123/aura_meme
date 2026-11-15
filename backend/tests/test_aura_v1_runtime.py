"""Aura V1 runs against real PostgreSQL with rollback-only fixtures."""
from datetime import timedelta
from uuid import UUID, uuid4
import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session
from test_auth import auth, migrated, register, login, csrf
from test_blog import blog, admin, create_post, mutation

@pytest.fixture
def v1(admin):
    from app.aura_runtime import publish_v1
    client, connection, owner, *_ = admin
    with Session(bind=connection, join_transaction_mode="create_savepoint") as db:
        policy=publish_v1(db,owner,client.app.state.auth.now())
        db.commit()
    return admin

@pytest.mark.integration
def test_published_runtime_initializes_actual_empty_ledger_and_checkin(v1):
    client, connection, owner, *_ = v1
    before=client.get('/api/v1/aura/progress')
    assert before.status_code==200, before.text
    assert before.json()['total_xp']==0 and before.json()['level']==1
    first=mutation(client,'POST','/aura/check-in')
    assert first.status_code==200, first.text
    assert first.json()['earned_xp_delta']==15 and first.json()['khi_van_delta']==0
    again=mutation(client,'POST','/aura/check-in')
    assert again.status_code==200 and again.json()['already_checked_in'] and again.json()['earned_xp_delta']==0
    after=client.get('/api/v1/aura/progress').json()
    assert (after['earned_xp'],after['bonus_xp'],after['level'],after['level_xp'],after['xp_to_next'],after['checked_in'])==(15,0,2,4,8,True)
    assert connection.scalar(text('SELECT count(*) FROM wallets'))==0
    assert connection.scalar(text('SELECT count(*) FROM wallet_transactions'))==0
    assert connection.execute(text('SELECT reward_mode,wallet_transaction_id FROM daily_checkins')).one()==('aura_v1',None)

@pytest.mark.integration
def test_registration_after_publication_has_real_zero_progress(v1):
    client, connection, *_=v1
    client.cookies.clear()
    created=register(client,username='bob_v1',email='bob-v1@example.com')
    assert created.status_code==201
    assert login(client,email='bob-v1@example.com').status_code==200
    response=client.get('/api/v1/aura/progress')
    assert response.status_code==200,response.text
    assert response.json()['total_xp']==0 and not response.json()['checked_in']
    assert response.json()['realm']=='Luyện Khí'


def other_member(connection,now,index):
    from app.models import User,Profile
    ident=uuid4()
    connection.execute(User.__table__.insert().values(id=ident,username=f'v1_member_{index}',email=f'v1_{index}@example.com',password_hash='synthetic',status='active',created_at=now,updated_at=now))
    connection.execute(Profile.__table__.insert().values(user_id=ident,display_name='Synthetic',updated_at=now))
    return ident


def source_post(db,owner,category,now):
    from app.models import Post
    row=Post(id=uuid4(),author_id=owner,category_id=category,title='Synthetic post',content='Synthetic body',status='published',created_at=now,updated_at=now)
    db.add(row);db.flush();return row

@pytest.mark.integration
def test_independent_stream_caps_135_and_reversals_do_not_refill(v1):
    from app.aura_runtime import active_policy,award_post,award_reaction,award_comment,claim_checkin,progress_payload,reverse_post
    from app.models import PostReaction,Comment
    client,connection,owner,category,*_=v1
    now=client.app.state.auth.now()
    peers=[other_member(connection,now,i) for i in range(21)]
    with Session(bind=connection,join_transaction_mode='create_savepoint') as db:
        own=[source_post(db,owner,category,now) for _ in range(3)]
        for row in own:award_post(db,row,now)
        for peer in peers:
            db.add(PostReaction(post_id=own[0].id,user_id=peer,reaction_type='like',created_at=now,updated_at=now));db.flush()
            award_reaction(db,own[0].id,peer,now)
            comment=Comment(id=uuid4(),post_id=own[0].id,author_id=peer,body='Synthetic',status='visible',created_at=now,updated_at=now)
            db.add(comment);db.flush();award_comment(db,comment,now)
        others=[source_post(db,peers[0],category,now) for _ in range(11)]
        for row in others:
            db.add(PostReaction(post_id=row.id,user_id=owner,reaction_type='like',created_at=now,updated_at=now));db.flush();award_reaction(db,row.id,owner,now)
            comment=Comment(id=uuid4(),post_id=row.id,author_id=owner,body='Synthetic',status='visible',created_at=now,updated_at=now)
            db.add(comment);db.flush();award_comment(db,comment,now)
        claim_checkin(db,owner,now)
        data=progress_payload(db,owner,now)
        assert (data['earned_xp'],data['bonus_xp'])==(135,0)
        reverse_post(db,own[0].id,now)
        reduced=progress_payload(db,owner,now)['earned_xp']
        assert reduced==55
        for row in own:award_post(db,row,now)
        assert progress_payload(db,owner,now)['earned_xp']==reduced
        assert db.scalar(text("SELECT count(*) FROM aura_ledger WHERE user_id=:id AND base_xp>0 AND event_type='post'"),{'id':owner})==2
        assert db.scalar(text("SELECT count(*) FROM aura_ledger WHERE bonus_xp<>0 OR multiplier_at_event<>1 OR tier_at_event<>'FREE'"))==0

@pytest.mark.integration
def test_social_api_self_nonself_retry_remove_readd_and_comment_delete(v1):
    client,connection,owner,*_=v1
    own=create_post(v1,status='published');assert own.status_code==201,own.text
    ident=own.json()['id']
    assert mutation(client,'PUT',f'/posts/{ident}/reactions',{'reaction_type':'like'}).status_code==200
    assert client.get('/api/v1/aura/progress').json()['total_xp']==10
    client.cookies.clear()
    assert register(client,username='bob_v1',email='bob-v1@example.com').status_code==201
    assert login(client,email='bob-v1@example.com').status_code==200
    path=f'/posts/{ident}/reactions'
    for kind in ['like','love','love']:
        assert mutation(client,'PUT',path,{'reaction_type':kind}).status_code==200
    assert client.get('/api/v1/aura/progress').json()['total_xp']==1
    assert mutation(client,'DELETE',path).status_code==204
    assert mutation(client,'PUT',path,{'reaction_type':'fire'}).status_code==200
    assert client.get('/api/v1/aura/progress').json()['total_xp']==0
    first=mutation(client,'POST',f'/posts/{ident}/comments',{'body':'Valid comment'})
    assert first.status_code==201,first.text
    assert mutation(client,'POST',f'/posts/{ident}/comments',{'body':'Second comment'}).status_code==201
    assert client.get('/api/v1/aura/progress').json()['total_xp']==2
    assert mutation(client,'DELETE','/comments/'+first.json()['id']).status_code==204
    assert client.get('/api/v1/aura/progress').json()['total_xp']==0
    assert mutation(client,'POST',f'/posts/{ident}/comments',{'body':'Third comment'}).status_code==201
    assert client.get('/api/v1/aura/progress?user_id='+str(owner)).json()['total_xp']==0
    assert connection.scalar(text('SELECT aura_xp_earned FROM user_progress WHERE user_id=:id'),{'id':owner})==10

@pytest.mark.integration
def test_streak_timezone_reset_missed_day_and_no_wallet(v1):
    from app.aura_runtime import claim_checkin,progress_payload
    client,connection,owner,*_=v1
    now=client.app.state.auth.now()
    with Session(bind=connection,join_transaction_mode='create_savepoint') as db:
        assert claim_checkin(db,owner,now)['streak_days']==1
        assert claim_checkin(db,owner,now+timedelta(days=1,seconds=-1))['already_checked_in']
        assert claim_checkin(db,owner,now+timedelta(days=1))['streak_days']==2
        assert progress_payload(db,owner,now+timedelta(days=4))['streak_days']==0
        assert claim_checkin(db,owner,now+timedelta(days=4))['streak_days']==1
        assert progress_payload(db,owner,now+timedelta(days=4))['total_xp']==45

@pytest.mark.integration
def test_checkin_security_and_rollback_on_receipt_failure(v1):
    client,connection,*_=v1
    assert client.post('/api/v1/aura/check-in').status_code==403
    token=csrf(client)
    assert client.post('/api/v1/aura/check-in',headers={'Origin':'https://evil.invalid','X-CSRF-Token':token}).status_code==403
    connection.exec_driver_sql("CREATE FUNCTION aura_test_reject() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'synthetic failure' USING ERRCODE='23514'; END $$")
    connection.exec_driver_sql('CREATE TRIGGER aura_test_reject BEFORE INSERT ON daily_checkins FOR EACH ROW EXECUTE FUNCTION aura_test_reject()')
    assert mutation(client,'POST','/aura/check-in').status_code==500
    assert connection.scalar(text('SELECT count(*) FROM aura_ledger'))==0
    assert connection.scalar(text('SELECT aura_xp_earned FROM user_progress'))==0
    client.cookies.clear()
    assert mutation(client,'POST','/aura/check-in').status_code==401

@pytest.mark.integration
def test_preexisting_sources_are_baselined_and_immutable(admin):
    from app.aura_runtime import publish_v1,award_post
    from sqlalchemy.exc import IntegrityError
    client,connection,owner,*_=admin
    old=create_post(admin,status='published');assert old.status_code==201
    with Session(bind=connection,join_transaction_mode='create_savepoint') as db:
        from app.models import Post
        now=client.app.state.auth.now()
        publish_v1(db,owner,now)
        award_post(db,db.get(Post,UUID(old.json()['id'])),now)
        assert db.scalar(text('SELECT count(*) FROM aura_ledger'))==0
        assert db.scalar(text('SELECT count(*) FROM aura_reward_events'))==1
        with pytest.raises(IntegrityError),db.begin_nested():db.execute(text('DELETE FROM aura_reward_events'))


@pytest.mark.integration
def test_retired_earning_policy_does_not_block_exact_reversal(v1):
    from app.aura_runtime import reverse_post
    client,connection,owner,*_=v1
    created=create_post(v1,status='published');assert created.status_code==201
    connection.execute(text("UPDATE reward_policy_versions SET status='retired' WHERE status='published'"))
    with Session(bind=connection,join_transaction_mode='create_savepoint') as db:
        reverse_post(db,UUID(created.json()['id']),client.app.state.auth.now())
        reverse_post(db,UUID(created.json()['id']),client.app.state.auth.now())
        assert db.scalar(text('SELECT aura_xp_earned FROM user_progress WHERE user_id=:owner'),{'owner':owner})==0
        assert db.scalar(text("SELECT count(*) FROM aura_ledger WHERE event_type='reversal'"))==1


@pytest.mark.integration
def test_admin_created_account_has_actual_zero_progress(v1):
    from test_auth import PASSWORD
    client,*_=v1
    result=mutation(client,'POST','/admin/users',{'username':'created_v1','email':'created-v1@example.com','password':PASSWORD,'display_name':'Created V1','roles':['USER']})
    assert result.status_code==201,result.text
    client.cookies.clear()
    assert login(client,email='created-v1@example.com').status_code==200
    response=client.get('/api/v1/aura/progress')
    assert response.status_code==200,response.text
    assert response.json()['total_xp']==0

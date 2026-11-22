from vault_test_rights import synthetic_rights
"""Meme reaction unit checks are DB-free; integration drafts require approved isolated 0011."""
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import Mock
from uuid import UUID, uuid4

from pydantic import ValidationError
import pytest
from sqlalchemy.dialects import postgresql

from app.blog_schemas import PostInteractions, REACTION_TYPES
from app.interactions import ReactionInput, ReactionResult
from app.comment_reactions import CommentInteractions
from app.meme_reactions import meme_reaction_states, reaction_statement, set_owned_reaction, valid_meme_reaction
from app.models import PostReaction, CommentReaction
from app.security import AuthError


def request(enabled=True):
    return SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(vault=SimpleNamespace(vault_runtime_enabled=enabled))),
                           url_for=lambda name, **kwargs: 'https://testserver/api/v1/catalog/assets/' + str(kwargs['asset_id']))


@pytest.mark.parametrize('kind', REACTION_TYPES)
def test_standard_payload_and_response_keep_legacy_shape(kind):
    payload = ReactionInput(reaction_type=kind, user_id=str(uuid4()), xp=999)
    assert payload.model_dump() == {'reaction_type': kind}
    assert ReactionResult(post_id=uuid4(), **payload.model_dump()).model_dump()['reaction_type'] == kind


@pytest.mark.parametrize('body', [
    {'reaction_type': 'meme'}, {'reaction_type': 'meme', 'meme_asset_id': 'not-a-uuid'},
    {'reaction_type': 'like', 'meme_asset_id': str(uuid4())}, {'reaction_type': 'unknown'},
])
def test_meme_and_standard_fields_must_match(body):
    with pytest.raises(ValidationError):
        ReactionInput(**body)


@pytest.mark.parametrize('model,target', [(PostReaction, 'post_id'), (CommentReaction, 'comment_id')])
def test_sql_same_row_idempotency_clears_meme_when_replacing_with_standard(model, target):
    now = datetime.now(timezone.utc)
    for kind, asset in [('meme', uuid4()), ('like', None)]:
        payload = ReactionInput(reaction_type=kind, meme_asset_id=asset)
        statement = reaction_statement(model, target, uuid4(), uuid4(), payload, now, True)
        sql = str(statement.compile(dialect=postgresql.dialect()))
        assert f'ON CONFLICT ({target}, user_id) DO UPDATE' in sql
        assert 'IS DISTINCT FROM' in sql and 'meme_asset_id =' in sql
        assert statement.compile().params['meme_asset_id'] == asset
        assert 'quantity' not in sql and 'aura_ledger' not in sql
    legacy = reaction_statement(model, target, uuid4(), uuid4(), ReactionInput(reaction_type='like'), now, False)
    assert 'meme_asset_id' not in str(legacy.compile(dialect=postgresql.dialect()))


def test_disabled_meme_refuses_before_any_database_access():
    account = SimpleNamespace(db=Mock(), user=SimpleNamespace(id=uuid4()))
    with pytest.raises(AuthError) as error:
        set_owned_reaction(account, request(False), PostReaction, 'post_id', uuid4(),
                           ReactionInput(reaction_type='meme', meme_asset_id=uuid4()), datetime.now(timezone.utc))
    assert error.value.status == 503
    account.db.execute.assert_not_called()
    account.db.scalar.assert_not_called()
    assert meme_reaction_states(account.db, PostReaction, [uuid4()], None, request(False)) == {}
    account.db.execute.assert_not_called()


@pytest.mark.parametrize('change', ['missing', 'zero', 'inactive', 'pending', 'wrong-kind'])
def test_unowned_or_unready_meme_never_writes(monkeypatch, change):
    import app.vault_runtime as runtime
    monkeypatch.setattr(runtime, 'require_enabled', lambda *args: None)
    item = SimpleNamespace(quantity=0 if change == 'zero' else 2)
    asset = SimpleNamespace(kind='frame' if change == 'wrong-kind' else 'avatar',
                            active=change != 'inactive', source_rights={'review_status': 'pending' if change == 'pending' else 'approved'})
    db = Mock()
    db.scalar.side_effect = [None if change == 'missing' else item, asset]
    account = SimpleNamespace(db=db, user=SimpleNamespace(id=uuid4()))
    with pytest.raises(AuthError) as error:
        set_owned_reaction(account, request(), PostReaction, 'post_id', uuid4(),
                           ReactionInput(reaction_type='meme', meme_asset_id=uuid4()), datetime.now(timezone.utc))
    assert error.value.status == 404
    db.execute.assert_not_called()
    assert item.quantity == (0 if change == 'zero' else 2)


def test_aggregate_is_one_owner_filtered_query_without_actor_identity(monkeypatch):
    import app.vault_runtime as runtime
    monkeypatch.setattr(runtime, 'require_schema', lambda db: None)
    targets = [uuid4(), uuid4()]
    asset = SimpleNamespace(id=uuid4(), slug='synthetic', kind='avatar', rarity='D', display_name='Ảnh thử', effect_key=None, active=True, source_rights=synthetic_rights('a'*64))
    db = Mock()
    db.execute.return_value.all.return_value = [(targets[0], asset, 3, 1)]
    state = meme_reaction_states(db, PostReaction, targets, uuid4(), request())
    db.execute.assert_called_once()
    sql = str(db.execute.call_args.args[0].compile(dialect=postgresql.dialect(), compile_kwargs={'literal_binds': True}))
    for term in ('user_inventory.quantity >', 'users.status =', 'asset_items.active IS true', 'GROUP BY', 'review_status'):
        assert term in sql
    assert state[targets[0]]['viewer_meme_asset_id'] == asset.id
    assert state[targets[0]]['meme_reactions'][0]['count'] == 3
    assert state[targets[1]] == {'viewer_meme_asset_id': None, 'meme_reactions': []}
    assert 'source_rights' not in state[targets[0]]['meme_reactions'][0]['asset'].model_dump()


def test_legacy_viewer_type_stays_six_or_null_and_new_fields_omit_when_disabled():
    counts = dict.fromkeys(REACTION_TYPES, 0)
    post = PostInteractions(post_id=uuid4(), reaction_counts=counts, comments_count=0, viewer_reaction='meme', bookmarked=False)
    comment = CommentInteractions(comment_id=uuid4(), reaction_counts=counts, viewer_reaction='meme')
    for dto in (post, comment):
        assert dto.viewer_reaction is None
        body = dto.model_dump()
        assert body['viewer_reaction'] is None
        assert 'meme_reactions' not in body and 'viewer_meme_asset_id' not in body


def test_score_eligibility_query_filters_owned_active_approved_avatars():
    sql = str(valid_meme_reaction(PostReaction).compile(dialect=postgresql.dialect(), compile_kwargs={'literal_binds': True}))
    for term in ('user_inventory.user_id = post_reactions.user_id', 'user_inventory.quantity >',
                 'asset_items.active IS true', 'asset_items.kind =', 'review_status'):
        assert term in sql


# Imported fixtures connect only when integration tests are explicitly selected and approved.
from test_auth import auth, migrated
from test_blog import blog, mutation
from test_comments import comments
from test_comment_reactions import target_comment


@pytest.fixture
def owned_meme_target(target_comment, monkeypatch):
    import json
    from sqlalchemy import text
    client, connection, owner, comment_id, post_id, _ = target_comment
    assert connection.scalar(text('SELECT version_num FROM alembic_version')) == '0014_premium_sandbox', 'Review and migrate isolated test DB first.'
    monkeypatch.setattr(client.app.state, 'vault', SimpleNamespace(vault_runtime_enabled=True), raising=False)
    asset = uuid4()
    rights = synthetic_rights('a'*64,name_review_status='approved')
    connection.execute(text("INSERT INTO asset_items (id,slug,kind,collection,rarity,media_key,source_rights,active,created_at,updated_at,display_name) VALUES (:id,'reaction-fixture','avatar','synthetic','D',:key,CAST(:rights AS jsonb),true,now(),now(),'Ảnh thử')"),
                       {'id': asset, 'key': 'catalog/' + 'a' * 64 + '.png', 'rights': json.dumps(rights)})
    connection.execute(text('INSERT INTO user_inventory (user_id,asset_id,quantity,acquired_at,updated_at) VALUES (:owner,:asset,3,now(),now())'), {'owner': owner, 'asset': asset})
    return client, connection, owner, asset, post_id, comment_id


@pytest.mark.integration
@pytest.mark.parametrize('target_kind', ['posts', 'comments'])
def test_persisted_owned_meme_retry_replace_counts_remove_without_consuming(owned_meme_target, target_kind):
    from sqlalchemy import text
    client, connection, owner, asset, post_id, comment_id = owned_meme_target
    target = post_id if target_kind == 'posts' else comment_id
    table = 'post_reactions' if target_kind == 'posts' else 'comment_reactions'
    path = f'/{target_kind}/{target}/reactions'
    for _ in range(2):
        response = mutation(client, 'PUT', path, {'reaction_type': 'meme', 'meme_asset_id': str(asset)})
        assert response.status_code == 200, response.text
    assert connection.scalar(text('SELECT count(*) FROM ' + table)) == 1
    before = connection.execute(text('SELECT created_at,updated_at FROM ' + table)).one()
    assert mutation(client, 'PUT', path, {'reaction_type': 'meme', 'meme_asset_id': str(asset)}).status_code == 200
    assert connection.execute(text('SELECT created_at,updated_at FROM ' + table)).one() == before
    state = client.get(f'/api/v1/{target_kind}/{target}/interactions').json()
    assert state['viewer_reaction'] is None and state['viewer_meme_asset_id'] == str(asset)
    assert state['meme_reactions'][0]['count'] == 1 and state['reaction_counts'] == dict.fromkeys(REACTION_TYPES, 0)
    assert mutation(client, 'PUT', path, {'reaction_type': 'love'}).status_code == 200
    assert connection.scalar(text('SELECT meme_asset_id FROM ' + table)) is None
    assert mutation(client, 'DELETE', path).status_code == 204
    assert mutation(client, 'DELETE', path).status_code == 204
    assert connection.scalar(text('SELECT quantity FROM user_inventory WHERE user_id=:owner AND asset_id=:asset'), {'owner': owner, 'asset': asset}) == 3
    assert connection.scalar(text('SELECT count(*) FROM aura_ledger')) == 0


@pytest.mark.integration
@pytest.mark.parametrize('target_kind', ['posts', 'comments'])
@pytest.mark.parametrize('invalid', ['unowned', 'zero', 'inactive', 'pending', 'wrong-kind', 'hidden-target'])
def test_persisted_meme_refuses_nonowned_unready_or_hidden_targets(owned_meme_target, target_kind, invalid):
    from sqlalchemy import text
    client, connection, owner, asset, post_id, comment_id = owned_meme_target
    if invalid == 'unowned':
        connection.execute(text('DELETE FROM user_inventory WHERE user_id=:owner AND asset_id=:asset'), {'owner': owner, 'asset': asset})
    elif invalid == 'zero':
        connection.execute(text('UPDATE user_inventory SET quantity=0 WHERE asset_id=:asset'), {'asset': asset})
    elif invalid == 'inactive':
        connection.execute(text('UPDATE asset_items SET active=false WHERE id=:asset'), {'asset': asset})
    elif invalid == 'pending':
        connection.execute(text("UPDATE asset_items SET active=false,source_rights=jsonb_set(source_rights,'{review_status}','\"pending\"') WHERE id=:asset"), {'asset': asset})
    elif invalid == 'wrong-kind':
        connection.execute(text('DELETE FROM user_inventory WHERE user_id=:owner AND asset_id=:asset'), {'owner': owner, 'asset': asset})
        connection.execute(text("UPDATE asset_items SET kind='frame' WHERE id=:asset"), {'asset': asset})
        connection.execute(text('INSERT INTO user_inventory (user_id,asset_id,quantity,acquired_at,updated_at) VALUES (:owner,:asset,3,now(),now())'), {'owner': owner, 'asset': asset})
    else:
        connection.execute(text("UPDATE posts SET status='hidden' WHERE id=:post"), {'post': post_id})
    target = post_id if target_kind == 'posts' else comment_id
    response = mutation(client, 'PUT', f'/{target_kind}/{target}/reactions', {'reaction_type': 'meme', 'meme_asset_id': str(asset)})
    assert response.status_code == 404, response.text
    assert connection.scalar(text('SELECT count(*) FROM post_reactions')) == 0
    assert connection.scalar(text('SELECT count(*) FROM comment_reactions')) == 0


@pytest.mark.integration
@pytest.mark.parametrize('target_kind', ['posts', 'comments'])
def test_persisted_meme_keeps_session_csrf_and_owner_guards(owned_meme_target, target_kind):
    client, _, _, asset, post_id, comment_id = owned_meme_target
    target = post_id if target_kind == 'posts' else comment_id
    path = f'/api/v1/{target_kind}/{target}/reactions'
    body = {'reaction_type': 'meme', 'meme_asset_id': str(asset)}
    assert client.put(path, json=body).status_code == 403
    client.cookies.clear()
    assert client.put(path, json=body).status_code == 401


def test_standard_replacement_clears_meme_reference_even_when_issuance_disabled(monkeypatch):
    import app.vault_runtime as runtime
    monkeypatch.setattr(runtime, 'schema_ready', lambda db: True)
    db = Mock()
    account = SimpleNamespace(db=db, user=SimpleNamespace(id=uuid4()))
    set_owned_reaction(account, request(False), PostReaction, 'post_id', uuid4(),
                       ReactionInput(reaction_type='like'), datetime.now(timezone.utc))
    statement = db.execute.call_args.args[0]
    assert statement.compile().params['meme_asset_id'] is None
    assert 'meme_asset_id =' in str(statement.compile(dialect=postgresql.dialect()))

@pytest.mark.integration
def test_owned_meme_post_reaction_uses_one_shared_aura_claim(owned_meme_target):
    from sqlalchemy import text
    from sqlalchemy.orm import Session
    from app.aura_runtime import publish_v1
    from test_auth import register, login
    client,connection,author,asset,post_id,comment_id=owned_meme_target
    now=client.app.state.auth.now()
    role=uuid4()
    connection.execute(text("INSERT INTO roles VALUES (:role,'ADMIN','Synthetic fixture admin')"),{'role':role})
    connection.execute(text('INSERT INTO user_roles VALUES (:owner,:role,:now)'),{'owner':author,'role':role,'now':now})
    with Session(bind=connection,join_transaction_mode='create_savepoint') as db,db.begin():
        publish_v1(db,author,now)
    client.cookies.clear()
    response=register(client,username='meme_actor_v1',email='meme-actor-v1@example.com')
    assert response.status_code==201,response.text
    actor=UUID(response.json()['id'])
    assert login(client,email='meme-actor-v1@example.com').status_code==200
    connection.execute(text('INSERT INTO user_inventory VALUES (:owner,:asset,3,:now,:now)'),{'owner':actor,'asset':asset,'now':now})
    path=f'/posts/{post_id}/reactions'
    body={'reaction_type':'meme','meme_asset_id':str(asset)}
    for value in (body,body,{'reaction_type':'like'},body):
        response=mutation(client,'PUT',path,value)
        assert response.status_code==200,response.text
    for owner,expected in ((actor,1),(author,2)):
        assert connection.scalar(text('SELECT aura_xp_earned FROM user_progress WHERE user_id=:owner'),{'owner':owner})==expected
    assert mutation(client,'DELETE',path).status_code==204
    assert mutation(client,'PUT',path,{'reaction_type':'like'}).status_code==200
    assert mutation(client,'PUT',path,body).status_code==200
    assert connection.scalar(text("SELECT count(*) FROM aura_reward_events WHERE kind='reaction' AND actor_id=:actor AND post_id=:post"),{'actor':actor,'post':post_id})==1
    assert connection.scalar(text("SELECT count(*) FROM aura_ledger WHERE event_type='reaction'"))==2
    assert connection.scalar(text("SELECT count(*) FROM aura_ledger WHERE event_type='reversal'"))==2
    assert connection.scalar(text('SELECT sum(aura_xp_earned) FROM user_progress'))==0
    assert mutation(client,'PUT',f'/comments/{comment_id}/reactions',body).status_code==200
    assert connection.scalar(text('SELECT count(*) FROM aura_ledger'))==4
    assert connection.scalar(text('SELECT quantity FROM user_inventory WHERE user_id=:owner AND asset_id=:asset'),{'owner':actor,'asset':asset})==3

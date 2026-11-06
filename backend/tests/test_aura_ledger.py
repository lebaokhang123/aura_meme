"""Draft-only simulation; fixture values are not an approved product economy."""
from datetime import timedelta
from uuid import UUID, uuid4

import pytest
from sqlalchemy import text

from test_auth import auth, migrated
from test_blog import blog, create_post


@pytest.fixture
def draft(blog):
    client, connection, owner, _, _ = blog
    post = UUID(create_post(blog, status="published").json()["id"])
    policy = uuid4()
    connection.execute(text("INSERT INTO reward_policy_versions VALUES (:id,1,CAST(:config AS jsonb),'draft',:now,:owner,:now)"), {
        "id": policy, "owner": owner, "now": client.app.state.auth.now(),
        "config": '{"xp":{"post":7,"reaction":3,"comment":4},"daily_cap":20,"levels":[0,10,30]}',
    })
    from sqlalchemy.orm import Session
    with Session(bind=connection, join_transaction_mode="create_savepoint") as db:
        yield client, db, owner, post, policy


@pytest.mark.integration
def test_draft_reward_retries_keep_one_event_and_atomic_progress(draft):
    from app.aura import simulate_reward
    client, db, owner, post, policy = draft
    now = client.app.state.auth.now()
    first = simulate_reward(db, policy, "post", post, owner, now)
    again = simulate_reward(db, policy, "post", post, owner, now + timedelta(seconds=1))
    assert first.id == again.id and first.base_xp == 7 and first.bonus_xp == 0
    assert db.scalar(text("SELECT count(*) FROM aura_ledger")) == 1
    assert db.execute(text("SELECT aura_xp_earned,aura_xp_bonus,aura_xp_total,level_cached,fair_level_cached FROM user_progress")).one() == (7, 0, 7, 1, 1)


@pytest.mark.integration
def test_full_reversal_is_once_and_never_reopens_reward_identity(draft):
    from app.aura import simulate_reward, simulate_reversal
    client, db, owner, post, policy = draft
    now = client.app.state.auth.now()
    first = simulate_reward(db, policy, "post", post, owner, now)
    reversal = simulate_reversal(db, first.id, now + timedelta(seconds=1))
    assert reversal.base_xp == -7 and reversal.reverses_id == first.id
    assert simulate_reversal(db, first.id, now + timedelta(seconds=2)).id == reversal.id
    assert simulate_reward(db, policy, "post", post, owner, now).id == first.id
    assert db.scalar(text("SELECT aura_xp_total FROM user_progress")) == 0
    assert db.scalar(text("SELECT count(*) FROM aura_ledger")) == 2


@pytest.mark.integration
def test_ledger_update_and_delete_are_rejected_by_database(draft):
    from app.aura import simulate_reward
    from sqlalchemy.exc import IntegrityError
    client, db, owner, post, policy = draft
    simulate_reward(db, policy, "post", post, owner, client.app.state.auth.now())
    for sql in ("UPDATE aura_ledger SET base_xp=999", "DELETE FROM aura_ledger"):
        with pytest.raises(IntegrityError), db.begin_nested():
            db.execute(text(sql))
    assert db.scalar(text("SELECT base_xp FROM aura_ledger")) == 7


@pytest.mark.integration
def test_ledger_truncate_is_rejected_before_data_loss(draft):
    from app.aura import simulate_reward
    from sqlalchemy.exc import IntegrityError
    client, db, owner, post, policy = draft
    simulate_reward(db, policy, "post", post, owner, client.app.state.auth.now())
    with pytest.raises(IntegrityError), db.begin_nested():
        db.execute(text("TRUNCATE aura_ledger"))
    assert db.scalar(text("SELECT count(*) FROM aura_ledger")) == 1


@pytest.mark.parametrize("change", [{"levels": [1, 2]}, {"levels": [0, 0]}, {"levels": [0, -1]},
    {"daily_cap": True}, {"daily_cap": 0}, {"daily_cap": 2**40}, {"xp": {"post": "7"}}, {"unexpected": 1}])
def test_draft_policy_rejects_ambiguous_config(change):
    from app.aura import DraftPolicy
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        DraftPolicy.model_validate({"xp": {"post": 7}, "daily_cap": 20, "levels": [0, 10]} | change)


@pytest.mark.integration
@pytest.mark.parametrize("status", ["published", "retired"])
def test_simulation_never_uses_a_published_or_retired_policy(draft, status):
    from app.aura import simulate_reward
    client, db, owner, post, policy = draft
    db.execute(text("UPDATE reward_policy_versions SET status=:status"), {"status": status})
    with pytest.raises(ValueError, match="draft"):
        simulate_reward(db, policy, "post", post, owner, client.app.state.auth.now())
    assert db.scalar(text("SELECT count(*) FROM aura_ledger")) == 0
    assert db.scalar(text("SELECT count(*) FROM user_progress")) == 0


@pytest.mark.integration
def test_policy_snapshot_can_only_retire_without_mutating_config(draft):
    from sqlalchemy.exc import IntegrityError
    _, db, _, _, _ = draft
    db.execute(text("UPDATE reward_policy_versions SET status='published'"))
    for sql in ("UPDATE reward_policy_versions SET version=2", "DELETE FROM reward_policy_versions",
                "UPDATE reward_policy_versions SET status='retired', config_json='{}'::jsonb"):
        with pytest.raises(IntegrityError), db.begin_nested():
            db.execute(text(sql))
    db.execute(text("UPDATE reward_policy_versions SET status='retired'"))
    with pytest.raises(IntegrityError), db.begin_nested():
        db.execute(text("UPDATE reward_policy_versions SET status='draft'"))


@pytest.mark.integration
@pytest.mark.parametrize("problem", ["self_reaction", "missing_reaction", "deleted_post", "future", "naive", "missing_comment", "wrong_post_actor"])
def test_invalid_sources_or_time_do_not_create_progress(draft, problem):
    from app.aura import simulate_reward
    client, db, owner, post, policy = draft
    now = client.app.state.auth.now()
    kind, actor, source = "post", owner, post
    if problem == "self_reaction":
        kind = "reaction"
        db.execute(text("INSERT INTO post_reactions VALUES (:post,:owner,'like',:now,:now)"), {"post": post, "owner": owner, "now": now})
    if problem in {"missing_reaction", "wrong_post_actor"}:
        actor = uuid4()
        db.execute(text("INSERT INTO users VALUES (:id,'sim_actor','sim-actor@example.com','synthetic','active',:now,:now,NULL)"), {"id": actor, "now": now})
        if problem == "missing_reaction": kind = "reaction"
    if problem == "deleted_post": db.execute(text("UPDATE posts SET status='deleted',deleted_at=:now"), {"now": now})
    if problem == "future": now -= timedelta(days=1)
    if problem == "naive": now = now.replace(tzinfo=None)
    if problem == "missing_comment": kind, source = "comment", uuid4()
    # Nonpublic source uses the same safe 404 exception as Blog, not an eligibility response.
    from app.security import AuthError
    with pytest.raises((ValueError, AuthError)):
        simulate_reward(db, policy, kind, source, actor, now)
    assert db.scalar(text("SELECT count(*) FROM aura_ledger")) == 0
    assert db.scalar(text("SELECT count(*) FROM user_progress")) == 0


@pytest.mark.integration
def test_generated_total_and_reversal_ownership_are_database_constraints(draft):
    from app.aura import simulate_reward
    from app.models import AuraLedger
    from sqlalchemy.exc import DBAPIError, IntegrityError
    client, db, owner, post, policy = draft
    original = simulate_reward(db, policy, "post", post, owner, client.app.state.auth.now())
    with pytest.raises(DBAPIError), db.begin_nested():
        db.execute(text("UPDATE user_progress SET aura_xp_total=999"))
    other = uuid4()
    db.execute(text("INSERT INTO users VALUES (:id,'sim_other','sim-other@example.com','synthetic','active',now(),now(),NULL)"), {"id": other})
    values = {column.name: getattr(original, column.name) for column in AuraLedger.__table__.columns}
    values.update(id=uuid4(), user_id=other, event_key='synthetic-reversal', event_type='reversal', base_xp=-7, reverses_id=original.id)
    with pytest.raises(IntegrityError) as error, db.begin_nested():
        db.execute(AuraLedger.__table__.insert().values(**values))
    assert error.value.orig.diag.constraint_name == 'fk_aura_ledger_owner_reversal'


@pytest.mark.integration
def test_failed_reversal_leaves_no_pending_entry_when_caller_continues(draft):
    from app.aura import simulate_reward, simulate_reversal
    from app.models import UserProgress
    client, db, owner, post, policy = draft
    now = client.app.state.auth.now()
    original = simulate_reward(db, policy, "post", post, owner, now)
    cached = db.get(UserProgress, owner)
    assert cached.aura_xp_earned == 7
    db.execute(text("UPDATE user_progress SET aura_xp_earned=0"))
    with pytest.raises(ValueError, match="negative"):
        simulate_reversal(db, original.id, now)
    db.flush()
    assert db.scalar(text("SELECT count(*) FROM aura_ledger")) == 1


@pytest.mark.integration
def test_database_rejection_of_cache_rolls_back_ledger_too(draft):
    from app.aura import simulate_reward
    from sqlalchemy.exc import IntegrityError
    client, db, owner, post, policy = draft
    db.execute(text("CREATE FUNCTION m61b_reject_cache() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'Synthetic cache rejection' USING ERRCODE='23514'; END $$"))
    db.execute(text("CREATE TRIGGER m61b_reject_cache BEFORE INSERT ON user_progress FOR EACH ROW EXECUTE FUNCTION m61b_reject_cache()"))
    with pytest.raises(IntegrityError):
        simulate_reward(db, policy, 'post', post, owner, client.app.state.auth.now())
    assert db.scalar(text('SELECT count(*) FROM aura_ledger')) == 0
    assert db.scalar(text('SELECT count(*) FROM user_progress')) == 0


@pytest.mark.integration
def test_source_dependency_locks_refresh_already_loaded_post(draft):
    from app.comments import lock_public_post
    from app.models import Post
    _, db, _, post_id, _ = draft
    cached = db.get(Post, post_id)
    new_category = uuid4()
    db.execute(text("INSERT INTO categories VALUES (:id,'sim-moved','Moved','active',now(),now())"), {"id": new_category})
    db.execute(text("UPDATE posts SET category_id=:category WHERE id=:id"), {"category": new_category, "id": post_id})
    assert cached.category_id != new_category
    lock_public_post(db, post_id)
    assert cached.category_id == new_category


def test_target_guard_runs_before_savepoint_can_flush_caller_state():
    from app.aura import simulate_reward
    from datetime import datetime, timezone
    class WrongTarget:
        def execute(self, statement):
            class Result:
                def one(self): return ('aurameme_dev', 'public')
            return Result()
        def begin_nested(self):
            raise AssertionError('Savepoint would flush pending ORM data before target validation')
    with pytest.raises(ValueError, match='only on isolated'):
        simulate_reward(WrongTarget(), uuid4(), 'post', uuid4(), uuid4(), datetime.now(timezone.utc))


@pytest.mark.integration
def test_source_author_is_rechecked_after_lock_refresh(draft):
    from app.aura import simulate_reward
    from app.models import Post
    client, db, owner, post, policy = draft
    cached, other = db.get(Post, post), uuid4()
    now = client.app.state.auth.now()
    db.execute(text("INSERT INTO users VALUES (:id,'sim_new_owner','sim-new-owner@example.com','synthetic','active',:now,:now,NULL)"), {"id": other, "now": now})
    db.execute(text("INSERT INTO profiles(user_id,display_name,updated_at) VALUES (:id,'New owner',:now)"), {"id": other, "now": now})
    db.execute(text("UPDATE posts SET author_id=:owner WHERE id=:id"), {"owner": other, "id": post})
    assert cached.author_id == owner
    with pytest.raises(ValueError, match='source'):
        simulate_reward(db, policy, 'post', post, owner, now)
    assert db.scalar(text('SELECT count(*) FROM aura_ledger')) == 0


@pytest.mark.integration
def test_disappeared_comment_source_is_rejected_without_partial_cache(draft):
    from app.aura import simulate_reward
    from app.models import Comment
    client, db, _, post, policy = draft
    actor, source, now = uuid4(), uuid4(), client.app.state.auth.now()
    db.execute(text("INSERT INTO users VALUES (:id,'sim_commenter','sim-commenter@example.com','synthetic','active',:now,:now,NULL)"), {"id": actor, "now": now})
    db.execute(text("INSERT INTO comments VALUES (:id,:post,:actor,'Synthetic','visible',:now,:now,NULL)"), {"id": source, "post": post, "actor": actor, "now": now})
    cached = db.get(Comment, source)
    db.execute(text('DELETE FROM comments WHERE id=:id'), {'id': source})
    with pytest.raises(ValueError, match='source'):
        simulate_reward(db, policy, 'comment', source, actor, now)
    assert cached.id == source
    assert db.scalar(text('SELECT count(*) FROM user_progress')) == 0


@pytest.mark.integration
@pytest.mark.parametrize("tamper", ["disable", "function"])
def test_schema_guard_rejects_changed_immutable_objects(draft, tamper):
    from schema_guard import assert_auxiliary_objects
    _, db, *_ = draft
    with pytest.raises(AssertionError), db.begin_nested():
        if tamper == "disable":
            db.execute(text("ALTER TABLE aura_ledger DISABLE TRIGGER aura_ledger_immutable"))
        else:
            db.execute(text("CREATE OR REPLACE FUNCTION aurameme_immutable_ledger() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RETURN OLD; END $$"))
        assert_auxiliary_objects(db)
    assert_auxiliary_objects(db)


@pytest.mark.integration
@pytest.mark.parametrize("days", [7, 30, 90])
def test_draft_days_simulation_preserves_cap_and_cache(draft, days):
    from app.aura import simulate_reward
    client, db, owner, post, policy = draft
    now = client.app.state.auth.now()
    for day in range(days):
        for index in range(3):
            source = uuid4()
            db.execute(text("INSERT INTO posts SELECT :id,author_id,category_id,NULL,'Synthetic simulation','Text','published',:now,:now,NULL FROM posts WHERE id=:post"), {"id": source, "now": now + timedelta(days=day), "post": post})
            if index < 2:
                simulate_reward(db, policy, "post", source, owner, now + timedelta(days=day))
            else:
                with pytest.raises(ValueError, match="cap"):
                    simulate_reward(db, policy, "post", source, owner, now + timedelta(days=day))
    assert db.scalar(text("SELECT count(*) FROM aura_ledger")) == days * 2
    assert db.scalar(text("SELECT SUM(base_xp) FROM aura_ledger")) == days * 14
    assert db.scalar(text("SELECT aura_xp_total FROM user_progress")) == days * 14


@pytest.mark.integration
def test_simulation_refuses_development_with_real_readonly_connection(migrated):
    from app.aura import simulation_only
    from app.config import load_settings
    from app.db import create_db_engine
    from datetime import datetime, timezone
    from test_migrations import development_inventory
    engine = create_db_engine(load_settings())
    try:
        before = development_inventory(engine)
        with engine.connect() as connection:
            connection.exec_driver_sql("SET TRANSACTION READ ONLY")
            with pytest.raises(ValueError, match="only on isolated"):
                simulation_only(connection, datetime.now(timezone.utc))
        assert development_inventory(engine) == before
    finally:
        engine.dispose()


@pytest.mark.integration
@pytest.mark.parametrize("kind", ["reaction", "comment"])
def test_confirmed_foreign_source_retries_do_not_farm_rewards(draft, kind):
    from app.aura import simulate_reward
    client, db, owner, post, policy = draft
    now, actor, source = client.app.state.auth.now(), uuid4(), post
    db.execute(text("INSERT INTO users VALUES (:id,'sim_reactor','sim-reactor@example.com','synthetic','active',:now,:now,NULL)"), {"id": actor, "now": now})
    if kind == "reaction":
        db.execute(text("INSERT INTO post_reactions VALUES (:post,:actor,'like',:now,:now)"), {"post": post, "actor": actor, "now": now})
    else:
        source = uuid4()
        db.execute(text("INSERT INTO comments VALUES (:id,:post,:actor,'Synthetic comment','visible',:now,:now,NULL)"), {"id": source, "post": post, "actor": actor, "now": now})
    first = simulate_reward(db, policy, kind, source, actor, now)
    if kind == "reaction":
        db.execute(text("DELETE FROM post_reactions"))
        db.execute(text("INSERT INTO post_reactions VALUES (:post,:actor,'fire',:now,:now)"), {"post": post, "actor": actor, "now": now})
    else:
        db.execute(text("UPDATE comments SET status='deleted',deleted_at=:now"), {"now": now})
    assert simulate_reward(db, policy, kind, source, actor, now + timedelta(seconds=1)).id == first.id
    assert db.scalar(text("SELECT count(*) FROM aura_ledger")) == 1
    assert db.scalar(text("SELECT aura_xp_earned FROM user_progress")) == (3 if kind == "reaction" else 4)

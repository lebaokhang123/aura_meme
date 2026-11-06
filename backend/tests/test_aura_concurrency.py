"""Draft fixture mechanics on committed, independent PostgreSQL connections."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from threading import Event
from uuid import UUID, uuid4

import pytest
from sqlalchemy import event, text
from sqlalchemy.orm import Session

from app.aura import simulate_reward
from test_auth import migrated
from test_comments_concurrency import race_comments, wait_for_lock


@pytest.mark.integration
@pytest.mark.parametrize("second_kind", ["post", "reaction"])
def test_draft_replay_and_cap_are_serialized_by_recipient(race_comments, second_kind):
    owner_client, actor_client, engine, post_id, tag = race_comments
    owner = UUID(owner_client.get('/api/v1/users/me').json()['id'])
    actor = UUID(actor_client.get('/api/v1/users/me').json()['id'])
    policy, now = uuid4(), datetime.now(timezone.utc)
    with engine.begin() as connection:
        connection.execute(text("INSERT INTO reward_policy_versions VALUES (:id,1,CAST(:config AS jsonb),'draft',:now,:owner,:now)"), {"id": policy, "owner": owner, "now": now, "config": '{"xp":{"post":7,"reaction":3},"daily_cap":7,"levels":[0,10]}'})
        connection.execute(text("INSERT INTO post_reactions VALUES (:post,:actor,'like',:now,:now)"), {"post": post_id, "actor": actor, "now": now})
    locked, release = Event(), Event()
    def pause(conn, cursor, statement, parameters, context, executemany):
        if 'FROM users' in statement and 'FOR UPDATE' in statement and not locked.is_set():
            locked.set()
            assert release.wait(7)
    event.listen(engine, 'after_cursor_execute', pause)
    def reward(kind, identity):
        with Session(engine) as db, db.begin():
            try:
                return simulate_reward(db, policy, kind, post_id, identity, now).id
            except ValueError as fault:
                assert 'cap' in str(fault)
                return 'capped'
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            first = pool.submit(reward, 'post', owner)
            try:
                assert locked.wait(5)
                second = pool.submit(reward, second_kind, owner if second_kind == 'post' else actor)
                wait_for_lock(engine, tag)
            finally:
                release.set()
            result = first.result(timeout=15)
            assert second.result(timeout=15) == (result if second_kind == 'post' else 'capped')
        with engine.connect() as connection:
            assert connection.scalar(text('SELECT count(*) FROM aura_ledger WHERE policy_id=:id'), {'id': policy}) == 1
            assert connection.scalar(text('SELECT aura_xp_total FROM user_progress WHERE user_id=:id'), {'id': owner}) == 7
    finally:
        release.set()
        event.remove(engine, 'after_cursor_execute', pause)
        # Only privileged isolated fixture cleanup bypasses this one trigger, transactionally.
        with engine.begin() as connection:
            assert connection.scalar(text('SELECT count(*) FROM aura_ledger WHERE policy_id=:policy AND (user_id<>:owner OR source_post_id<>:post)'), {'policy': policy, 'owner': owner, 'post': post_id}) == 0
            connection.exec_driver_sql('ALTER TABLE aura_ledger DISABLE TRIGGER aura_ledger_immutable')
            connection.execute(text('DELETE FROM aura_ledger WHERE policy_id=:id'), {'id': policy})
            connection.exec_driver_sql('ALTER TABLE aura_ledger ENABLE TRIGGER aura_ledger_immutable')
            connection.execute(text('DELETE FROM user_progress WHERE user_id=:id'), {'id': owner})
            connection.execute(text('DELETE FROM reward_policy_versions WHERE id=:id'), {'id': policy})
            connection.execute(text('DELETE FROM post_reactions WHERE post_id=:post AND user_id=:actor'), {'post': post_id, 'actor': actor})

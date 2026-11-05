"""Moderation vs comment creation through real APIs and independent PostgreSQL connections."""
from concurrent.futures import ThreadPoolExecutor
from threading import Event
from uuid import uuid4
import pytest
from sqlalchemy import event, select
from app.main import app
from app.models import AdminAuditLog, Comment, Role, User, UserRole
from test_auth import csrf, migrated
from test_blog import mutation
from test_comments_concurrency import race_comments, wait_for_lock


@pytest.fixture
def moderation(race_comments):
    owner,moderator,engine,post_id,tag=race_comments
    now=app.state.auth.now()
    with engine.begin() as connection:
        user_id=connection.scalar(select(User.id).where(User.username==moderator.get('/api/v1/users/me').json()['username']))
        role=uuid4()
        connection.execute(Role.__table__.insert().values(id=role,code="ADMIN",description="Synthetic moderator"))
        connection.execute(UserRole.__table__.insert().values(user_id=user_id,role_id=role,granted_at=now))
    try:yield race_comments
    finally:
        with engine.begin() as connection:
            connection.execute(AdminAuditLog.__table__.delete().where(AdminAuditLog.target_type=="post",AdminAuditLog.target_id==str(post_id)))


@pytest.mark.integration
@pytest.mark.parametrize("action", ["hide","delete"])
@pytest.mark.parametrize("winner", ["create","moderate"])
def test_comment_create_and_admin_visibility_are_serialized(moderation,action,winner):
    owner,admin,engine,post_id,tag=moderation
    tokens=[csrf(owner),csrf(admin)];locked,release=Event(),Event()
    target='FOR SHARE' if winner=='create' else 'FOR UPDATE'
    def pause(conn,cursor,statement,parameters,context,executemany):
        if 'FROM posts' in statement and target in statement and not locked.is_set():
            locked.set();assert release.wait(7)
    event.listen(engine,'after_cursor_execute',pause)
    def create():return mutation(owner,'POST',f'/posts/{post_id}/comments',{'body':'Concurrent comment'},tokens[0])
    def moderate():return mutation(admin,'PATCH' if action=='hide' else 'DELETE',f'/admin/posts/{post_id}',{'status':'hidden'} if action=='hide' else None,tokens[1])
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            first=pool.submit(create if winner=='create' else moderate)
            try:
                assert locked.wait(5)
                second=pool.submit(moderate if winner=='create' else create)
                wait_for_lock(engine,tag)
            finally:release.set()
            a,b=first.result(timeout=15),second.result(timeout=15)
        response=a if winner=='create' else b
        changed=b if winner=='create' else a
        assert response.status_code==(201 if winner=='create' else 404),response.text
        assert changed.status_code==(200 if action=='hide' else 204),changed.text
        assert owner.get(f'/api/v1/posts/{post_id}/comments').status_code==404
        with engine.connect() as connection:
            assert len(list(connection.scalars(select(Comment.id))))==(1 if winner=='create' else 0)
    finally:
        release.set();event.remove(engine,'after_cursor_execute',pause)


@pytest.mark.integration
def test_moderation_deferred_audit_commit_failure(moderation):
    from app.models import Post
    owner,admin,engine,post_id,tag=moderation
    try:
        with engine.begin() as connection:
            connection.exec_driver_sql("CREATE FUNCTION m41c_commit_fail() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'synthetic moderation commit'; END $$")
            connection.exec_driver_sql("CREATE CONSTRAINT TRIGGER m41c_commit_fail AFTER INSERT ON admin_audit_logs DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION m41c_commit_fail()")
        assert mutation(admin,'PATCH',f'/admin/posts/{post_id}',{'status':'hidden'}).status_code==500
        with engine.connect() as connection:
            assert connection.scalar(select(Post.status).where(Post.id==post_id))=='published'
            assert list(connection.scalars(select(AdminAuditLog.id)))==[]
    finally:
        with engine.begin() as connection:
            connection.exec_driver_sql('DROP TRIGGER m41c_commit_fail ON admin_audit_logs')
            connection.exec_driver_sql('DROP FUNCTION m41c_commit_fail()')

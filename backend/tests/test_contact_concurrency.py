"""Real committed Contact workflow with independent Admin connections and rollback."""
from concurrent.futures import ThreadPoolExecutor
from threading import Event
from uuid import UUID
import pytest
from sqlalchemy import event,select
from app.models import AdminAuditLog,ContactMessage
from test_auth import csrf,migrated
from test_blog import mutation
from test_admin_users_concurrency import admins
from test_comments_concurrency import wait_for_lock
from test_contact import send


@pytest.fixture
def contact_admins(admins):
    first,second,ids,engine,tag=admins
    response=send(first);assert response.status_code==201
    ident=UUID(response.json()['id'])
    try:yield first,second,engine,tag,ident
    finally:
        with engine.begin() as connection:
            connection.execute(ContactMessage.__table__.delete().where(ContactMessage.id==ident))


@pytest.mark.integration
def test_admin_status_updates_have_consistent_audit_chain(contact_admins):
    first,second,engine,tag,ident=contact_admins
    tokens=[csrf(first),csrf(second)];locked,release=Event(),Event()
    def pause(conn,cursor,statement,parameters,context,executemany):
        if 'FROM contact_messages' in statement and 'FOR UPDATE' in statement and not locked.is_set():
            locked.set();assert release.wait(7)
    event.listen(engine,'after_cursor_execute',pause)
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            a=pool.submit(mutation,first,'PATCH',f'/admin/contacts/{ident}',{'status':'in_review'},tokens[0])
            try:
                assert locked.wait(5)
                b=pool.submit(mutation,second,'PATCH',f'/admin/contacts/{ident}',{'status':'resolved'},tokens[1])
                wait_for_lock(engine,tag)
            finally:release.set()
            assert a.result(timeout=15).status_code==200 and b.result(timeout=15).status_code==200
        with engine.connect() as connection:
            assert connection.scalar(select(ContactMessage.status).where(ContactMessage.id==ident))=='resolved'
            rows=connection.execute(select(AdminAuditLog.before_json,AdminAuditLog.after_json).order_by(AdminAuditLog.created_at)).all()
            assert rows==[({'status':'new'},{'status':'in_review'}),({'status':'in_review'},{'status':'resolved'})]
    finally:release.set();event.remove(engine,'after_cursor_execute',pause)


@pytest.mark.integration
def test_admin_contact_deferred_audit_commit_rollback(contact_admins):
    first,second,engine,tag,ident=contact_admins
    try:
        with engine.begin() as connection:
            connection.exec_driver_sql("CREATE FUNCTION m42a_commit_fail() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'synthetic contact commit'; END $$")
            connection.exec_driver_sql('CREATE CONSTRAINT TRIGGER m42a_commit_fail AFTER INSERT ON admin_audit_logs DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION m42a_commit_fail()')
        assert mutation(first,'PATCH',f'/admin/contacts/{ident}',{'status':'resolved'}).status_code==500
        with engine.connect() as connection:
            assert connection.scalar(select(ContactMessage.status).where(ContactMessage.id==ident))=='new'
            assert list(connection.scalars(select(AdminAuditLog.id)))==[]
    finally:
        with engine.begin() as connection:
            connection.exec_driver_sql('DROP TRIGGER m42a_commit_fail ON admin_audit_logs')
            connection.exec_driver_sql('DROP FUNCTION m42a_commit_fail()')

"""Authenticated Contact and private Admin workflow against real PostgreSQL."""
from uuid import UUID,uuid4
from datetime import timedelta
import pytest
from sqlalchemy import select
from app.models import AdminAuditLog,AuthSession,ContactMessage
from test_auth import ORIGIN,auth,csrf,login,migrated,register
from test_blog import admin,blog,mutation

MESSAGE=dict(name="Synthetic Sender",email="sender@example.com",subject="Question",body="Private synthetic message")


def send(client,**changes):
    return mutation(client,"POST","/contact",MESSAGE|changes)


@pytest.mark.integration
def test_guest_contact_requires_authentication(auth):
    client,connection=auth
    response=send(client)
    assert response.status_code==401,response.text
    assert list(connection.scalars(select(ContactMessage.id)))==[]


@pytest.mark.integration
def test_authenticated_contact_links_session_user(blog):
    client,connection,user_id,*_=blog
    assert send(client).status_code==201
    assert connection.scalar(select(ContactMessage.user_id))==user_id


@pytest.mark.integration
@pytest.mark.parametrize('changes',[{'name':' '},{'subject':'\n'},{'body':'\t'},{'email':'bad'},
    {'name':'x'*101},{'subject':'x'*161},{'body':'x'*4001},{'body':None},{'body':1},{'body':'x\x00'},
    {'user_id':'forged'},{'status':'resolved'},{'roles':['ADMIN']}])
def test_contact_input_validation_and_identity_allowlist(blog,changes):
    client,connection,*_=blog
    response=send(client,**changes)
    assert response.status_code==422,response.text
    assert list(connection.scalars(select(ContactMessage.id)))==[]
    assert MESSAGE['email'] not in response.text and MESSAGE['body'] not in response.text


@pytest.mark.integration
@pytest.mark.parametrize('fault',['missing','bad','origin'])
def test_contact_session_csrf_and_origin(blog,fault):
    client,connection,*_=blog
    token=csrf(client)
    headers={'Origin':'https://evil.example' if fault=='origin' else ORIGIN,'X-CSRF-Token':'bad' if fault=='bad' else token}
    if fault=='missing':headers.pop('X-CSRF-Token')
    assert client.post('/api/v1/contact',json=MESSAGE,headers=headers).status_code==403
    assert list(connection.scalars(select(ContactMessage.id)))==[]


@pytest.mark.integration
@pytest.mark.parametrize('fault',['revoked','expired','pre_token'])
def test_user_contact_requires_live_session_binding(blog,fault):
    client,connection,actor,*_=blog
    token=csrf(client)
    if fault=='revoked':connection.execute(AuthSession.__table__.update().values(revoked_at=client.app.state.auth.now()))
    if fault=='expired':
        now=client.app.state.auth.now()
        connection.execute(AuthSession.__table__.update().values(created_at=now-timedelta(hours=1),expires_at=now-timedelta(seconds=1)))
    if fault=='pre_token':token=client.app.state.auth.csrf('pre:wrong')
    assert client.post('/api/v1/contact',json=MESSAGE,headers={'Origin':ORIGIN,'X-CSRF-Token':token}).status_code==(403 if fault=='pre_token' else 401)
    assert list(connection.scalars(select(ContactMessage.id)))==[]


@pytest.mark.integration
def test_contact_maximum_unicode_and_chunked_body_limit(blog):
    import json
    client,connection,*_=blog
    headers={'Origin':ORIGIN,'X-CSRF-Token':csrf(client),'Content-Type':'application/json'}
    response=client.post('/api/v1/contact',content=json.dumps(MESSAGE|{'body':'🐱'*4000}),headers=headers)
    assert response.status_code==201,response.text
    response=client.post('/api/v1/contact',content=iter([b'x'*33000,b'y'*33000]),headers=headers)
    assert response.status_code==422 and response.json()['error']['message']=='Request body too large.'
    assert len(list(connection.scalars(select(ContactMessage.id))))==1


@pytest.mark.integration
def test_no_public_contact_inbox(auth):
    client,connection=auth
    assert client.get('/api/v1/contact').status_code==405
    assert client.get('/api/v1/contact/'+str(uuid4())).status_code==404


@pytest.mark.integration
def test_contact_rate_limit(blog):
    client,connection,*_=blog
    codes=[send(client).status_code for _ in range(6)]
    assert codes==[201]*5+[429]
    assert len(list(connection.scalars(select(ContactMessage.id))))==5


@pytest.mark.integration
@pytest.mark.parametrize('identity',['anonymous','user'])
@pytest.mark.parametrize('method',['GET','PATCH'])
def test_contact_admin_privacy_rbac(blog,identity,method):
    client,connection,actor,*_=blog
    if identity=='anonymous':client.cookies.clear()
    response=client.get('/api/v1/admin/contacts') if method=='GET' else mutation(client,'PATCH','/admin/contacts/'+str(uuid4()),{'status':'resolved'})
    assert response.status_code==(401 if identity=='anonymous' else 403)
    assert MESSAGE['email'] not in response.text


@pytest.mark.integration
def test_admin_workflow_status_only_and_pii_free_audit(admin):
    client,connection,actor,*_=admin
    created=send(client).json();ident=created['id']
    result=client.get('/api/v1/admin/contacts').json()
    assert result['pagination']['total']==1
    assert set(result['items'][0])=={'id','name','email','subject','body','status','created_at'}
    for status in ['in_review','resolved','new']:
        response=mutation(client,'PATCH','/admin/contacts/'+ident,{'status':status})
        assert response.status_code==200 and response.json()['status']==status
    assert client.get('/api/v1/admin/contacts?status=resolved').json()['items']==[]
    audit=connection.execute(select(AdminAuditLog.__table__)).mappings().all()
    assert len(audit)==3
    assert all(set(row['before_json'])=={'status'} and set(row['after_json'])=={'status'} for row in audit)
    assert all(value not in str(audit) for value in MESSAGE.values())


@pytest.mark.integration
@pytest.mark.parametrize('values',[{}, {'status':None},{'status':'done'},{'status':'resolved','email':'forged@example.com'}])
def test_admin_contact_patch_strict_input(admin,values):
    client,*_=admin
    ident=send(client).json()['id']
    assert mutation(client,'PATCH','/admin/contacts/'+ident,values).status_code==422


@pytest.mark.integration
def test_admin_contact_page_bounds_filter_and_unknown_ids(admin):
    client,connection,*_=admin
    now=client.app.state.auth.now()
    connection.execute(ContactMessage.__table__.insert(),[dict(id=UUID(int=index),**MESSAGE,status='new',created_at=now,updated_at=now) for index in range(1,24)])
    page=client.get('/api/v1/admin/contacts?page_size=20').json()
    assert page['pagination']==dict(page=1,page_size=20,total=23,total_pages=2)
    assert [row['id'] for row in page['items']]==[str(UUID(int=index)) for index in range(23,3,-1)]
    for query in ('page=0','page_size=101','status=%00'):
        assert client.get('/api/v1/admin/contacts?'+query).status_code==422
    assert client.get('/api/v1/admin/contacts?page='+str(10**40)).json()['items']==[]
    assert client.get('/api/v1/admin/contacts?status=unknown').json()['items']==[]
    assert mutation(client,'PATCH','/admin/contacts/'+str(uuid4()),{'status':'resolved'}).status_code==404
    assert mutation(client,'PATCH','/admin/contacts/bad',{'status':'resolved'}).status_code==422


@pytest.mark.integration
@pytest.mark.parametrize('fault',['insert','audit'])
def test_contact_failure_rolls_back_without_pii(blog,fault):
    client,connection,*_=blog
    if fault=='insert':
        connection.exec_driver_sql("CREATE FUNCTION m42a_insert_fail() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'synthetic contact failure'; END $$")
        connection.exec_driver_sql('CREATE TRIGGER m42a_insert_fail BEFORE INSERT ON contact_messages FOR EACH ROW EXECUTE FUNCTION m42a_insert_fail()')
        response=send(client)
        assert response.status_code==500
        assert list(connection.scalars(select(ContactMessage.id)))==[]
        assert all(value not in response.text for value in MESSAGE.values())
    else:
        from app.models import Role,User,UserRole
        actor=connection.scalar(select(User.id));role=uuid4();now=client.app.state.auth.now()
        connection.execute(Role.__table__.insert().values(id=role,code='ADMIN',description='Synthetic admin'))
        connection.execute(UserRole.__table__.insert().values(user_id=actor,role_id=role,granted_at=now))
        ident=send(client).json()['id']
        connection.exec_driver_sql("CREATE FUNCTION m42a_audit_fail() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'synthetic contact audit'; END $$")
        connection.exec_driver_sql('CREATE TRIGGER m42a_audit_fail BEFORE INSERT ON admin_audit_logs FOR EACH ROW EXECUTE FUNCTION m42a_audit_fail()')
        assert mutation(client,'PATCH','/admin/contacts/'+ident,{'status':'resolved'}).status_code==500
        assert connection.scalar(select(ContactMessage.status))=='new'


def test_contact_openapi_requires_session_and_forbidden_response_declared():
    from app.main import app
    schema=app.openapi();operation=schema['paths']['/api/v1/contact']['post']
    assert operation.get('security')==[{'sessionCookie':[]}] and '401' in operation['responses'] and '403' in operation['responses']
    assert schema['components']['schemas']['ContactInput']['additionalProperties'] is False

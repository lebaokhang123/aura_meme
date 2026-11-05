"""Admin moderation and audit P0 contract on real PostgreSQL."""
from uuid import UUID, uuid4
import pytest
from sqlalchemy import select
from app.models import AdminAuditLog, Category, Comment, MediaUpload, Post, User
from test_auth import auth, migrated
from test_blog import admin, blog, create_post, mutation
from test_auth import csrf


@pytest.mark.integration
def test_admin_hides_and_deletes_post_preserving_comment_fk(admin):
    client, connection, actor, category, _ = admin
    ident = create_post(admin, status="published").json()["id"]
    comment_id = uuid4(); now = client.app.state.auth.now()
    connection.execute(Comment.__table__.insert().values(id=comment_id, post_id=UUID(ident), author_id=actor, body="Keep", status="visible", created_at=now, updated_at=now))
    response = mutation(client, "PATCH", "/admin/posts/" + ident, {"status": "hidden"})
    assert response.status_code == 200, response.text
    assert client.get("/api/v1/posts/" + ident).status_code == 404
    assert client.get(f"/api/v1/posts/{ident}/comments").status_code == 404
    assert mutation(client, "PATCH", "/admin/posts/" + ident, {"status": "published"}).status_code == 200
    assert client.get("/api/v1/posts/" + ident).status_code == 200
    assert mutation(client, "DELETE", "/admin/posts/" + ident).status_code == 204
    assert connection.scalar(select(Comment.post_id).where(Comment.id == comment_id)) == UUID(ident)
    row = connection.execute(select(Post.__table__).where(Post.id == UUID(ident))).mappings().one()
    assert row["status"] == "deleted" and row["deleted_at"] == row["updated_at"]
    assert mutation(client, "DELETE", "/admin/posts/" + ident).status_code == 404
    assert mutation(client, "PATCH", "/admin/posts/" + ident, {"status": "published"}).status_code == 404


@pytest.mark.integration
def test_admin_audit_response_excludes_snapshots(admin):
    client, connection, actor, *_ = admin
    connection.execute(AdminAuditLog.__table__.insert().values(id=uuid4(), actor_id=actor, action="test.synthetic", target_type="test", target_id="synthetic", before_json={"email":"synthetic-private@example.com"}, created_at=client.app.state.auth.now()))
    response=client.get("/api/v1/admin/audit-logs")
    assert response.status_code==200,response.text
    assert set(response.json()["items"][0])=={"id","actor_id","action","target_type","target_id","created_at"}
    assert "synthetic-private@example.com" not in response.text


@pytest.mark.integration
@pytest.mark.parametrize("method,path", [("GET","/admin/posts"),("GET","/admin/audit-logs"),
    ("PATCH","/admin/posts/00000000-0000-0000-0000-000000000001"),("DELETE","/admin/posts/00000000-0000-0000-0000-000000000001")])
@pytest.mark.parametrize("identity", ["anonymous","user"])
def test_moderation_and_audit_rbac(blog, method, path, identity):
    client, *_ = blog
    if identity=="anonymous":client.cookies.clear()
    response=client.get('/api/v1'+path) if method=="GET" else mutation(client,method,path,{"status":"hidden"})
    assert response.status_code==(401 if identity=="anonymous" else 403)


@pytest.mark.integration
@pytest.mark.parametrize("method", ["PATCH","DELETE"])
@pytest.mark.parametrize("problem", ["csrf","origin"])
def test_moderation_csrf_origin(admin,method,problem):
    client,*_=admin
    ident=create_post(admin,status="published").json()["id"]
    assert mutation(client,method,'/admin/posts/'+ident,{"status":"hidden"},token="bad" if problem=="csrf" else csrf(client),
                    origin="https://evil.example" if problem=="origin" else "https://testserver").status_code==403


@pytest.mark.integration
@pytest.mark.parametrize("values", [{},{"author_id":"forged"},{"status":"deleted"},{"status":None},
    {"title":" "},{"content":None},{"title":"x\x00"},{"media_id":"bad"},{"category_id":None}])
def test_admin_post_strict_patch(admin,values):
    client,*_=admin
    ident=create_post(admin).json()["id"]
    assert mutation(client,"PATCH",'/admin/posts/'+ident,values).status_code==422


@pytest.mark.integration
def test_admin_list_all_states_search_pagination_and_audit_metadata(admin):
    client,connection,actor,*_=admin
    ids=[]
    for title,status in [("Needle100%_","draft"),("Other","published"),("Last","draft")]:
        ids.append(create_post(admin,title=title,status=status).json()["id"])
    assert mutation(client,"PATCH",'/admin/posts/'+ids[-1],{"status":"hidden"}).status_code==200
    result=client.get('/api/v1/admin/posts?page_size=2').json()
    assert result['pagination']==dict(page=1,page_size=2,total=3,total_pages=2)
    assert [row['id'] for row in result['items']]==sorted(ids,reverse=True)[:2]
    assert client.get('/api/v1/admin/posts?status=hidden').json()['pagination']['total']==1
    assert client.get('/api/v1/admin/posts?search=%25').json()['pagination']['total']==1
    assert client.get('/api/v1/admin/posts?search=not-found').json()['items']==[]
    assert client.get('/api/v1/admin/posts?page='+str(10**40)).json()['items']==[]
    assert client.get('/api/v1/admin/audit-logs?page='+str(10**40)).json()['items']==[]
    for path in ('/admin/posts','/admin/audit-logs'):
        for query in ('page=0','page_size=101'):
            assert client.get('/api/v1'+path+'?'+query).status_code==422
    assert client.get('/api/v1/admin/posts?search=%00').status_code==422
    assert client.get('/api/v1/admin/posts?status=%00').status_code==422
    for method,payload in [("PATCH",{"status":"hidden"}),("DELETE",None)]:
        assert mutation(client,method,'/admin/posts/'+str(uuid4()),payload).status_code==404
        assert mutation(client,method,'/admin/posts/bad',payload).status_code==422


@pytest.mark.integration
def test_admin_media_validation_uses_post_author_and_keeps_visibility(admin):
    from fastapi.testclient import TestClient
    from app.main import app
    from test_auth import register
    client,connection,actor,category,hidden=admin
    other=TestClient(app,base_url="https://testserver")
    try:
        author=UUID(register(other,username="foreign_post",email="foreign-post@example.com").json()["id"])
    finally:other.close()
    post_id,owned,foreign=uuid4(),uuid4(),uuid4();now=client.app.state.auth.now()
    for ident,owner in [(owned,author),(foreign,actor)]:
        connection.execute(MediaUpload.__table__.insert().values(id=ident,owner_id=owner,object_key=str(ident),mime="image/png",size_bytes=1,status="ready",created_at=now,updated_at=now))
    connection.execute(Post.__table__.insert().values(id=post_id,author_id=author,category_id=hidden,title="Before",content="Text",status="published",created_at=now,updated_at=now))
    path='/admin/posts/'+str(post_id)
    response=mutation(client,"PATCH",path,{"media_id":str(owned),"content":"private-content-marker","title":"private-title-marker"})
    assert response.status_code==200,response.text
    assert response.json()['author']['id']==str(author) and 'email' not in response.json()['author']
    assert mutation(client,"PATCH",path,{"media_id":str(foreign)}).status_code==422
    connection.execute(MediaUpload.__table__.update().where(MediaUpload.id==owned).values(status="pending"))
    assert mutation(client,"PATCH",path,{"media_id":str(owned)}).status_code==422
    assert mutation(client,"PATCH",path,{"status":"hidden"}).status_code==200
    assert mutation(client,"PATCH",path,{"status":"published"}).status_code==200
    assert client.get('/api/v1/posts/'+str(post_id)).status_code==404
    audit=str(connection.execute(select(AdminAuditLog.__table__)).all())
    assert 'private-content-marker' not in audit and 'private-title-marker' not in audit
    assert connection.scalar(select(Post.author_id).where(Post.id==post_id))==author


@pytest.mark.integration
@pytest.mark.parametrize("method", ["PATCH","DELETE"])
def test_admin_post_audit_failure_rolls_back(admin,method):
    client,connection,*_=admin
    ident=UUID(create_post(admin,status="published").json()['id'])
    before=dict(connection.execute(select(Post.__table__).where(Post.id==ident)).mappings().one())
    connection.exec_driver_sql("CREATE FUNCTION m41c_audit_fail() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'synthetic moderation audit'; END $$")
    connection.exec_driver_sql("CREATE TRIGGER m41c_audit_fail BEFORE INSERT ON admin_audit_logs FOR EACH ROW EXECUTE FUNCTION m41c_audit_fail()")
    assert mutation(client,method,'/admin/posts/'+str(ident),{"status":"hidden"}).status_code==500
    assert dict(connection.execute(select(Post.__table__).where(Post.id==ident)).mappings().one())==before
    assert client.get('/api/v1/posts/'+str(ident)).status_code==200


@pytest.mark.integration
@pytest.mark.parametrize("path", ["/api/v1/admin/posts","/api/v1/admin/audit-logs"])
def test_admin_boundary_requires_https(admin,path):
    from fastapi.testclient import TestClient
    from app.main import app
    insecure=TestClient(app,base_url="http://testserver")
    try:assert insecure.get(path).status_code==403
    finally:insecure.close()


@pytest.mark.integration
def test_admin_post_body_boundary_preserves_legitimate_maximum(admin):
    import json
    client,*_=admin
    ident=create_post(admin).json()['id']
    headers={'Origin':'https://testserver','X-CSRF-Token':csrf(client),'Content-Type':'application/json'}
    path='/api/v1/admin/posts/'+ident
    assert client.patch(path,content=json.dumps({'content':'🐱'*20000}),headers=headers).status_code==200
    response=client.patch(path,content=b'x'*262145,headers=headers)
    assert response.status_code==422 and response.json()['error']['message']=='Request body too large.'

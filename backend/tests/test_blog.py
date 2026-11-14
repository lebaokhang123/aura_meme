"""Real PostgreSQL blog tests reuse the rollback-only Auth fixture."""
from datetime import timedelta
from uuid import UUID, uuid4

import pytest
from sqlalchemy import text

from app.models import AdminAuditLog, Category, Comment, MediaUpload, Post, Profile, Role, User, UserRole
from test_auth import ORIGIN, auth, csrf, login, migrated, register


@pytest.fixture
def blog(auth):
    client, connection = auth
    response = register(client)
    assert response.status_code == 201 and login(client).status_code == 200
    user_id = UUID(response.json()["id"])
    now = client.app.state.auth.now()
    category_id, hidden_id = uuid4(), uuid4()
    for category, slug, status in [(category_id, "active-cat", "active"), (hidden_id, "hidden-cat", "hidden")]:
        connection.execute(Category.__table__.insert().values(id=category, slug=slug, name=slug,
            status=status, created_at=now, updated_at=now))
    return client, connection, user_id, category_id, hidden_id


@pytest.fixture
def admin(blog):
    client, connection, user_id, *_ = blog
    role_id = uuid4()
    connection.execute(Role.__table__.insert().values(id=role_id, code="ADMIN", description="Synthetic admin"))
    connection.execute(UserRole.__table__.insert().values(user_id=user_id, role_id=role_id,
                                                       granted_at=client.app.state.auth.now()))
    return blog


def mutation(client, method, path, payload=None, token=None, origin=ORIGIN):
    return client.request(method, "/api/v1" + path, json=payload,
        headers={"Origin": origin, "X-CSRF-Token": token or csrf(client)})


def create_post(blog, **changes):
    client, _, _, category_id, _ = blog
    return mutation(client, "POST", "/posts", {"title": "Test title", "content": "Plain text", "category_id": str(category_id)} | changes)


@pytest.mark.integration
def test_public_categories_pagination_and_admin_audit(admin):
    client, connection, user_id, *_ = admin
    public = client.get("/api/v1/categories?page=1&page_size=1").json()
    assert public["pagination"] == {"page": 1, "page_size": 1, "total": 1, "total_pages": 1}
    assert public["items"][0]["status"] == "active"
    assert client.get("/api/v1/admin/categories?status=hidden&search=hidden").json()["pagination"]["total"] == 1
    created = mutation(client, "POST", "/admin/categories", {"name": "New", "slug": "new-cat"})
    assert created.status_code == 201 and created.json()["status"] == "active"
    category_id = created.json()["id"]
    assert mutation(client, "PATCH", "/admin/categories/" + category_id, {"name": "Renamed"}).status_code == 200
    assert mutation(client, "DELETE", "/admin/categories/" + category_id).status_code == 204
    assert client.get("/api/v1/admin/categories?search=Renamed").json()["items"][0]["status"] == "hidden"
    audits = connection.execute(text("SELECT actor_id,before_json,after_json FROM admin_audit_logs ORDER BY created_at,id")).all()
    assert len(audits) == 3 and all(row.actor_id == user_id for row in audits)
    assert sum(row.before_json is None for row in audits) == 1
    assert any(row.after_json["status"] == "hidden" for row in audits)
    assert mutation(client, "POST", "/admin/categories", {"name": "Duplicate", "slug": "new-cat"}).status_code == 409
    assert connection.execute(text("SELECT count(*) FROM admin_audit_logs")).scalar_one() == 3


@pytest.mark.integration
@pytest.mark.parametrize("kind,expected", [("anonymous", 401), ("user", 403)])
def test_admin_categories_denied_without_db_role(blog, kind, expected):
    client, connection, *_ = blog
    if kind == "anonymous":
        client.cookies.clear()
    assert client.get("/api/v1/admin/categories").status_code == expected
    for method,path,payload in [("POST", "/admin/categories", {"name": "No", "slug": "no"}),
        ("PATCH", "/admin/categories/" + str(uuid4()), {"name": "No"}),
        ("DELETE", "/admin/categories/" + str(uuid4()), None)]:
        assert mutation(client, method, path, payload).status_code == expected
    assert connection.execute(text("SELECT count(*) FROM admin_audit_logs")).scalar_one() == 0


@pytest.mark.integration
@pytest.mark.parametrize("payload", [{"name": " ", "slug": "ok"}, {"name": "x", "slug": "UPPER"},
    {"name": "x", "slug": "bad space"}, {"name": "x", "slug": "x" * 81},
    {"name": "x" * 81, "slug": "ok"}, {"name": "x", "slug": "ok", "status": "hidden"},
    {"name": "x", "slug": "ok", "unknown": 1}])
def test_category_input_validation(admin, payload):
    assert mutation(admin[0], "POST", "/admin/categories", payload).status_code == 422


@pytest.mark.integration
@pytest.mark.parametrize("payload", [{}, {"slug": "changed"}, {"status": None}, {"name": None}, {"name": " "}, {"status": "deleted"}])
def test_category_patch_allowlist(admin, payload):
    assert mutation(admin[0], "PATCH", "/admin/categories/" + str(admin[3]), payload).status_code == 422


@pytest.mark.integration
def test_audit_failure_rolls_back_category(admin):
    client, connection, *_ = admin
    connection.exec_driver_sql("CREATE FUNCTION public.m31_audit_fail() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'synthetic failure'; END $$")
    connection.exec_driver_sql("CREATE TRIGGER m31_fail BEFORE INSERT ON admin_audit_logs FOR EACH ROW EXECUTE FUNCTION public.m31_audit_fail()")
    assert mutation(client, "POST", "/admin/categories", {"name": "Rollback", "slug": "rollback"}).status_code == 500
    assert connection.execute(text("SELECT count(*) FROM categories WHERE slug='rollback'")).scalar_one() == 0
    assert connection.execute(text("SELECT count(*) FROM admin_audit_logs")).scalar_one() == 0


@pytest.mark.integration
def test_create_default_draft_author_timestamp_and_publish(blog):
    client, _, user_id, _, _ = blog
    response = create_post(blog)
    assert response.status_code == 201
    body = response.json();assert body["status"] == "draft" and body["author"]["id"] == str(user_id)
    assert set(body["author"]) == {"id", "username", "display_name", "created_at", "bio", "avatar_url"}
    assert body["media_url"] is None and body["created_at"] == body["updated_at"]
    assert "email" not in body["author"] and "comments_count" not in body
    path = "/posts/" + body["id"]
    assert client.get("/api/v1" + path).status_code == 404
    assert mutation(client, "PATCH", path, {"title": "Draft stays draft"}).json()["status"] == "draft"
    assert mutation(client, "PATCH", path, {"status": "published"}).status_code == 200
    assert client.get("/api/v1" + path).status_code == 200


@pytest.mark.integration
@pytest.mark.parametrize("changes", [{"author_id": str(uuid4())}, {"roles": ["ADMIN"]}, {"unknown": 1},
    {"status": "hidden"}, {"status": "deleted"}, {"status": None}, {"title": " "}, {"title": "x" * 161},
    {"content": " "}, {"content": "x" * 20001}, {"category_id": None}, {"category_id": str(uuid4())}])
def test_post_input_validation(blog, changes):
    response = create_post(blog, **changes)
    assert response.status_code == 422
    assert blog[1].execute(text("SELECT count(*) FROM posts")).scalar_one() == 0


@pytest.mark.integration
@pytest.mark.parametrize("kind", ["owned_ready", "owned_pending", "foreign", "missing"])
def test_post_media_and_content(blog, kind):
    client, connection, user_id, *_ = blog
    media_id, owner = uuid4(), user_id
    now = client.app.state.auth.now()
    if kind == "foreign":
        owner = uuid4()
        connection.execute(User.__table__.insert().values(id=owner, username="foreign", email="foreign@example.com", password_hash="test", status="active", created_at=now, updated_at=now))
    if kind != "missing":
        connection.execute(MediaUpload.__table__.insert().values(id=media_id, owner_id=owner, object_key="test/" + str(media_id), mime="image/png", size_bytes=1,
            status="pending" if kind == "owned_pending" else "ready", created_at=now, updated_at=now))
    response = create_post(blog, content="", media_id=str(media_id))
    assert response.status_code == (201 if kind == "owned_ready" else 422)
    if kind == "owned_ready":
        path = "/posts/" + response.json()["id"]
        assert mutation(client, "PATCH", path, {"media_id": None}).status_code == 422
        updated = mutation(client, "PATCH", path, {"media_id": None, "content": "Text now"})
        assert updated.status_code == 200 and updated.json()["media_url"] is None


@pytest.mark.integration
def test_hidden_category_and_post_visibility(blog):
    client, connection, user_id, category_id, hidden_id = blog
    assert create_post(blog, category_id=str(hidden_id)).status_code == 422
    ids = []
    now = client.app.state.auth.now()
    for status,category in [("published", category_id), ("draft", category_id), ("hidden", category_id), ("deleted", category_id), ("published", hidden_id)]:
        post_id = uuid4();ids.append(post_id)
        connection.execute(Post.__table__.insert().values(id=post_id, author_id=user_id, category_id=category, title="Visible?", content="Plain", status=status,
            created_at=now, updated_at=now, deleted_at=now if status=="deleted" else None))
    assert client.get("/api/v1/posts").json()["pagination"]["total"] == 1
    for post_id in ids[1:]:assert client.get("/api/v1/posts/" + str(post_id)).status_code == 404
    assert mutation(client, "PATCH", "/posts/" + str(ids[2]), {"status": "published"}).status_code == 404
    assert mutation(client, "PATCH", "/posts/" + str(ids[3]), {"status": "published"}).status_code == 404
    connection.execute(text("UPDATE users SET status='locked' WHERE id=:id"), {"id": user_id})
    assert client.get("/api/v1/posts").json()["items"] == []
    assert client.get("/api/v1/posts/" + str(ids[0])).status_code == 404


@pytest.mark.integration
def test_public_search_sort_pagination_and_literal_wildcards(blog):
    client, connection, user_id, category_id, _ = blog
    now = client.app.state.auth.now()
    ids = [uuid4() for _ in range(4)]
    for post_id,title,content in zip(ids,["Beta", "Alpha", "Alpha", "Percent%"],["needle", "body", "needle", "body"]):
        connection.execute(Post.__table__.insert().values(id=post_id, author_id=user_id, category_id=category_id, title=title, content=content,
            status="published", created_at=now, updated_at=now))
    ordered = client.get("/api/v1/posts?sort=created_asc&page_size=2").json()
    assert [item["id"] for item in ordered["items"]] == [str(i) for i in sorted(ids)[:2]]
    assert ordered["pagination"]["total"] == 4 and ordered["pagination"]["total_pages"] == 2
    assert client.get("/api/v1/posts?search=NEEDLE").json()["pagination"]["total"] == 2
    assert client.get("/api/v1/posts?search=%25").json()["pagination"]["total"] == 1
    assert client.get("/api/v1/posts?category=hidden-cat").json()["items"] == []
    assert client.get("/api/v1/posts?page=999999999999999999999999").json()["items"] == []
    assert [p["title"] for p in client.get("/api/v1/posts?sort=title_asc").json()["items"]] == ["Alpha", "Alpha", "Beta", "Percent%"]
    for query in ["page=0", "page_size=101", "page_size=0", "sort=title;DROP", "search=" + "x" * 101]:
        assert client.get("/api/v1/posts?" + query).status_code == 422


@pytest.mark.integration
def test_owner_patch_delete_retains_row_and_comment_fk(blog):
    client, connection, user_id, *_ = blog
    body = create_post(blog, status="published").json();post_id=UUID(body["id"])
    now = client.app.state.auth.now();client.app.state.auth.now=lambda:now+timedelta(minutes=1)
    updated=mutation(client,"PATCH","/posts/"+str(post_id),{"title":"Changed"})
    assert updated.status_code==200 and updated.json()["status"]=="published" and updated.json()["updated_at"]!=body["updated_at"]
    connection.execute(Comment.__table__.insert().values(id=uuid4(),post_id=post_id,author_id=user_id,body="existing comment",status="visible",created_at=now,updated_at=now))
    assert mutation(client,"DELETE","/posts/"+str(post_id)).status_code==204
    row=connection.execute(text("SELECT status,deleted_at,updated_at FROM posts WHERE id=:id"),{"id":post_id}).one()
    assert row.status=="deleted" and row.deleted_at==row.updated_at and row.deleted_at is not None
    assert connection.execute(text("SELECT count(*) FROM comments WHERE post_id=:id"),{"id":post_id}).scalar_one()==1
    assert mutation(client,"DELETE","/posts/"+str(post_id)).status_code==404
    assert client.get("/api/v1/posts/"+str(post_id)).status_code==404


@pytest.mark.integration
@pytest.mark.parametrize("payload", [{}, {"title":None}, {"content":None}, {"category_id":None}, {"status":None}, {"status":"hidden"}, {"author_id":str(uuid4())}])
def test_post_patch_allowlist_and_null(blog,payload):
    post_id=create_post(blog).json()["id"]
    assert mutation(blog[0],"PATCH","/posts/"+post_id,payload).status_code==422


@pytest.mark.integration
def test_idor_and_deleted_author_are_not_public(blog):
    client, connection, user_id, category_id, _ = blog
    now=client.app.state.auth.now();other=uuid4();post_id=uuid4()
    connection.execute(User.__table__.insert().values(id=other,username="other_author",email="other@example.com",password_hash="test",status="active",created_at=now,updated_at=now))
    connection.execute(Profile.__table__.insert().values(user_id=other,display_name="Other",updated_at=now))
    connection.execute(Post.__table__.insert().values(id=post_id,author_id=other,category_id=category_id,title="Other post",content="Body",status="published",created_at=now,updated_at=now))
    path="/posts/"+str(post_id)
    assert client.get("/api/v1"+path).status_code==200
    assert mutation(client,"PATCH",path,{"title":"Hijacked"}).status_code==404
    assert mutation(client,"DELETE",path).status_code==404
    connection.execute(text("UPDATE users SET status='deleted',deleted_at=:now WHERE id=:id"),{"id":other,"now":now})
    assert client.get("/api/v1"+path).status_code==404


@pytest.mark.integration
@pytest.mark.parametrize("route", ["post", "category"])
@pytest.mark.parametrize("kind", ["expired", "revoked"])
def test_csrf_origin_expired_and_revoked(admin, route, kind):
    client,connection,*_=admin
    if route=="post":
        path="/posts";payload={"title":"x","content":"x","category_id":str(admin[3])}
    else:
        path="/admin/categories";payload={"name":"x","slug":"new"}
    assert client.post("/api/v1"+path,json=payload,headers={"Origin":ORIGIN}).status_code==403
    assert mutation(client,"POST",path,payload,token="forged").status_code==403
    assert mutation(client,"POST",path,payload,origin="https://evil.example").status_code==403
    token=csrf(client)
    if kind=="revoked":
        connection.execute(text("UPDATE auth_sessions SET revoked_at=created_at"))
    else:
        now=client.app.state.auth.now();client.app.state.auth.now=lambda:now+timedelta(minutes=31)
    assert mutation(client,"POST",path,payload,token=token).status_code==401


@pytest.mark.integration
def test_post_transaction_rollback_and_full_content_limit(blog):
    client,connection,*_=blog
    response=create_post(blog,content="🔥"*20000)
    assert response.status_code==201 and len(response.json()["content"])==20000
    connection.exec_driver_sql("CREATE FUNCTION public.m31_post_fail() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'synthetic failure'; END $$")
    connection.exec_driver_sql("CREATE TRIGGER m31_fail BEFORE INSERT ON posts FOR EACH ROW EXECUTE FUNCTION public.m31_post_fail()")
    assert create_post(blog).status_code==500
    assert connection.execute(text("SELECT count(*) FROM posts")).scalar_one()==1


@pytest.mark.integration
def test_hidden_media_and_category_exclude_existing_posts(admin):
    client,connection,user_id,category_id,_=admin
    response=create_post(admin,status="published")
    post_id=response.json()["id"]
    assert client.get("/api/v1/posts/"+post_id).status_code==200
    assert mutation(client,"DELETE","/admin/categories/"+str(category_id)).status_code==204
    assert client.get("/api/v1/posts/"+post_id).status_code==404
    assert connection.execute(text("SELECT category_id FROM posts WHERE id=:id"),{"id":UUID(post_id)}).scalar_one()==category_id


@pytest.mark.integration
def test_anonymous_cannot_create_posts(blog):
    blog[0].cookies.clear()
    assert create_post(blog).status_code==401


@pytest.mark.integration
def test_public_posts_exact_author_filter(blog):
    from test_auth import ACCOUNT
    client,c,owner,category,_=blog
    published=create_post(blog,status='published')
    assert published.status_code==201,published.text
    assert create_post(blog,status='draft').status_code==201
    assert client.get('/api/v1/posts?author='+ACCOUNT['username']).json()['items']==[published.json()]
    assert client.get('/api/v1/posts?author='+ACCOUNT['username'][:-1]).json()['items']==[]
    assert client.get('/api/v1/posts?author=unknown_user').json()['items']==[]
    assert client.get('/api/v1/posts?author=%00').status_code==422

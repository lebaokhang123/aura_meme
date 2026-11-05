"""Real independent PostgreSQL connections for category/media/post races."""
from concurrent.futures import ThreadPoolExecutor
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select, update
from sqlalchemy.orm import Session

from app.main import app
from app.models import AdminAuditLog, AuthSession, Category, MediaUpload, Post, Profile, Role, User, UserRole
from test_auth import ORIGIN, csrf, login, migrated, register
from test_blog import mutation


@pytest.mark.integration
@pytest.mark.parametrize("race", ["category", "media", "post", "unique"])
def test_blog_races_preserve_visibility_and_integrity(migrated, monkeypatch, race):
    monkeypatch.setenv("AUTH_SIGNING_KEY", "test-only-signing-key-with-at-least-32-bytes")
    monkeypatch.setenv("AUTH_ENVIRONMENT", "production")
    monkeypatch.setenv("AUTH_ALLOWED_ORIGINS", '["https://testserver"]')
    engine=create_engine(migrated.url,hide_parameters=True,
        connect_args={"options":"-c statement_timeout=10000 -c lock_timeout=3000"})
    names=["race_"+uuid4().hex[:16] for _ in range(2)]
    category_id,media_id=uuid4(),uuid4();role_ids=[];slug="race-"+uuid4().hex
    with TestClient(app,base_url=ORIGIN) as first:
        app.state.auth_session_factory=lambda:Session(engine)
        second=TestClient(app,base_url=ORIGIN)
        try:
            with Session(engine) as db:assert db.scalar(select(Role.id)) is None
            response=register(first,username=names[0],email=names[0]+"@example.com");assert response.status_code==201
            owner=UUID(response.json()["id"]);assert login(first,email=names[0]+"@example.com").status_code==200
            other=owner
            if race in {"category","unique"}:
                response=register(second,username=names[1],email=names[1]+"@example.com");assert response.status_code==201
                other=UUID(response.json()["id"]);assert login(second,email=names[1]+"@example.com").status_code==200
            elif race=="post":
                assert login(second,email=names[0]+"@example.com").status_code==200
            now=app.state.auth.now()
            with Session(engine) as db,db.begin():
                if race in {"category","unique"}:
                    admin_role=Role(id=uuid4(),code="ADMIN",description="Synthetic admin")
                    db.add(admin_role);db.flush()
                    for user in ({other,owner} if race=="unique" else {other}):
                        db.add(UserRole(user_id=user,role_id=admin_role.id,granted_at=now))
                role_ids=list(db.scalars(select(Role.id)).all())
                if race!="unique":
                    db.add(Category(id=category_id,slug=slug,name="Race",status="active",created_at=now,updated_at=now))
                if race=="media":
                    db.add(MediaUpload(id=media_id,owner_id=owner,object_key=slug,mime="image/png",size_bytes=1,status="ready",created_at=now,updated_at=now))
            payload={"title":"Race","content":"Text","category_id":str(category_id),"status":"published"}
            a_csrf=csrf(first);b_csrf=csrf(second) if race!="media" else None
            post_id=None
            if race=="post":
                response=mutation(first,"POST","/posts",payload,token=a_csrf);assert response.status_code==201
                post_id=response.json()["id"]
            def reject_media():
                with Session(engine) as db,db.begin():
                    db.execute(update(MediaUpload).where(MediaUpload.id==media_id).values(status="rejected"))
                return 204
            with ThreadPoolExecutor(max_workers=2) as pool:
                if race=="unique":
                    a=pool.submit(mutation,first,"POST","/admin/categories",{"name":"Race","slug":slug},a_csrf)
                    b=pool.submit(mutation,second,"POST","/admin/categories",{"name":"Race","slug":slug},b_csrf)
                elif race=="post":
                    a=pool.submit(mutation,first,"PATCH","/posts/"+post_id,{"title":"Updated"},a_csrf)
                    b=pool.submit(mutation,second,"DELETE","/posts/"+post_id,None,b_csrf)
                else:
                    if race=="media":payload["media_id"]=str(media_id)
                    a=pool.submit(mutation,first,"POST","/posts",payload,a_csrf)
                    b=pool.submit(reject_media) if race=="media" else pool.submit(mutation,second,"DELETE","/admin/categories/"+str(category_id),None,b_csrf)
                ra,rb=a.result(timeout=15),b.result(timeout=15)
            if race=="unique":
                assert sorted([ra.status_code,rb.status_code])==[201,409]
                with Session(engine) as db:
                    assert len(db.scalars(select(Category).where(Category.slug==slug)).all())==1
                    assert len(db.scalars(select(AdminAuditLog)).all())==1
            elif race=="post":
                assert ra.status_code in {200,404} and rb.status_code==204
                with Session(engine) as db:
                    row=db.get(Post,UUID(post_id));assert row.status=="deleted" and row.deleted_at is not None
            else:
                assert ra.status_code in {201,422}
                assert (rb if race=="media" else rb.status_code)==204
                assert first.get("/api/v1/posts").json()["items"]==[]
        finally:
            with Session(engine) as db,db.begin():
                ids=list(db.scalars(select(User.id).where(User.username.in_(names))).all())
                db.execute(AdminAuditLog.__table__.delete().where(AdminAuditLog.actor_id.in_(ids)))
                db.execute(Post.__table__.delete().where(Post.author_id.in_(ids)))
                db.execute(MediaUpload.__table__.delete().where(MediaUpload.owner_id.in_(ids)))
                db.execute(Category.__table__.delete().where(Category.slug==slug))
                for model,column in [(AuthSession,AuthSession.user_id),(UserRole,UserRole.user_id),(Profile,Profile.user_id),(User,User.id)]:
                    db.execute(model.__table__.delete().where(column.in_(ids)))
                for role in role_ids:
                    assert db.scalar(select(UserRole.user_id).where(UserRole.role_id==role)) is None
                    db.execute(Role.__table__.delete().where(Role.id==role))
            second.close();engine.dispose()

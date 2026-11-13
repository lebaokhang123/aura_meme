"""Server-owned Social integration contracts and rollback API cases."""
from uuid import uuid4,UUID
import pytest
from sqlalchemy import text
from app.blog_schemas import PostInput
from test_auth import auth,migrated,register,login
from test_blog import admin,blog,create_post,mutation
from test_comments import comments,add

def test_composer_contract_accepts_no_title_and_optional_request_id():
    value=PostInput(content="Hello",category_id=uuid4(),request_id=uuid4())
    assert value.title is None and value.request_id is not None

@pytest.mark.integration
def test_title_retry_conflict_and_update_without_faking_author(blog):
    client,c,owner,category,_=blog;ident=uuid4()
    payload={"content":"Dòng đầu\nNội dung","category_id":str(category),"status":"published","request_id":str(ident)}
    for _ in range(2):
        response=mutation(client,"POST","/posts",payload);assert response.status_code==201
        assert response.json()["id"]==str(ident) and response.json()["title"]=="Dòng đầu"
        assert response.json()["author"]["id"]==str(owner)
    assert c.scalar(text("SELECT count(*) FROM posts"))==1
    assert mutation(client,"POST","/posts",payload|{"content":"Different"}).status_code==409
    updated=mutation(client,"PATCH",f"/posts/{ident}",{"content":"New content"})
    assert updated.status_code==200 and updated.json()["title"]=="New content"
    client.cookies.clear()
    assert register(client,username="other_owner",email="other-owner@example.com").status_code==201
    assert login(client,email="other-owner@example.com").status_code==200
    assert mutation(client,"POST","/posts",payload|{"content":"New content"}).status_code==409
    assert c.scalar(text("SELECT author_id FROM posts WHERE id=:id"),{"id":ident})==owner

@pytest.mark.integration
def test_hot_new_search_category_counts_are_from_visible_database_posts(blog):
    client,c,_,category,hidden=blog
    first=create_post(blog,title="First",content="Công nghệ 🔥",status="published").json()
    second=create_post(blog,title="Second",content="No keyword",status="published").json()
    c.execute(text("UPDATE posts SET created_at=created_at-interval '1 minute' WHERE id=:id"),{"id":UUID(first["id"])})
    assert client.get("/api/v1/posts?sort=created_desc").json()["items"][0]["id"]==second["id"]
    assert mutation(client,"PUT",f"/posts/{first['id']}/reactions",{"reaction_type":"love"}).status_code==200
    assert client.get("/api/v1/posts?sort=reaction_desc").json()["items"][0]["id"]==first["id"]
    assert [r["id"] for r in client.get("/api/v1/posts?search=cong%20nghe").json()["items"]]==[first["id"]]
    cats=client.get("/api/v1/categories").json()["items"]
    assert next(r for r in cats if r["id"]==str(category))["post_count"]==2
    assert mutation(client,"DELETE",f"/posts/{first['id']}").status_code==204
    cats=client.get("/api/v1/categories").json()["items"]
    assert next(r for r in cats if r["id"]==str(category))["post_count"]==1
    assert client.get("/api/v1/posts?page=2&page_size=1").json()["items"]==[]

@pytest.mark.integration
def test_comment_retry_and_payload_conflict(comments):
    client,c,_,post_id,_=comments;ident=uuid4()
    payload={"body":"A real comment 🔥","request_id":str(ident)}
    for _ in range(2):
        response=mutation(client,"POST",f"/posts/{post_id}/comments",payload)
        assert response.status_code==201 and response.json()["id"]==str(ident)
    assert c.scalar(text("SELECT count(*) FROM comments"))==1
    assert mutation(client,"POST",f"/posts/{post_id}/comments",payload|{"body":"Changed"}).status_code==409

@pytest.mark.integration
def test_feed_can_embed_session_owned_interactions_without_extra_http_calls(blog):
    client,c,_,category,_=blog
    post=create_post(blog,status="published").json()["id"]
    assert mutation(client,"PUT",f"/posts/{post}/reactions",{"reaction_type":"angry"}).status_code==200
    dto=client.get("/api/v1/posts?include_interactions=true").json()["items"][0]
    assert dto["interactions"]["reaction_counts"]["angry"]==1
    assert dto["interactions"]["viewer_reaction"]=="angry"
    client.cookies.clear()
    dto=client.get("/api/v1/posts?include_interactions=true").json()["items"][0]
    assert dto["interactions"]["viewer_reaction"] is None
    assert dto["interactions"]["reaction_counts"]["angry"]==1

@pytest.mark.integration
def test_admin_comment_moderation_is_rbac_audited_and_soft_deleted(admin):
    client,c,owner,category,_=admin
    post=create_post(admin,status="published").json()["id"]
    saved=dict(client.cookies);client.cookies.clear()
    assert register(client,username="ordinary_actor",email="ordinary@example.com").status_code==201
    assert login(client,email="ordinary@example.com").status_code==200
    ident=add(client,post).json()["id"]
    path=f"/admin/comments/{ident}"
    assert mutation(client,"PATCH",path,{"status":"hidden"}).status_code==403
    assert mutation(client,"PATCH",f"/posts/{post}",{"content":"IDOR"}).status_code==404
    client.cookies.clear();client.cookies.update(saved)
    assert mutation(client,"PATCH",path,{"status":"hidden"}).status_code==204
    assert client.get(f"/api/v1/posts/{post}/comments").json()["items"]==[]
    assert mutation(client,"PUT",f"/comments/{ident}/reactions",{"reaction_type":"fire"}).status_code==404
    assert mutation(client,"PATCH",path,{"status":"visible"}).status_code==204
    assert mutation(client,"DELETE",path).status_code==204
    row=c.execute(text("SELECT status,body,deleted_at FROM comments WHERE id=:id"),{"id":UUID(ident)}).one()
    assert row.status=="deleted" and row.body and row.deleted_at is not None
    assert c.scalar(text("SELECT count(*) FROM admin_audit_logs WHERE target_type='comment'"))==3

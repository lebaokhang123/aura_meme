"""Integration drafts: require reviewed0010 on isolated, empty aurameme_test."""
from uuid import UUID,uuid4
import pytest
from sqlalchemy import text
from test_auth import auth,migrated,register,login,ORIGIN,csrf
from test_blog import blog,mutation
from test_comments import comments,add

KINDS=("like","love","laugh","fire","sad","angry")

@pytest.fixture
def target_comment(comments):
    client,connection,owner,post_id,category=comments
    result=add(client,post_id);assert result.status_code==201
    return client,connection,owner,UUID(result.json()["id"]),post_id,category

@pytest.mark.integration
@pytest.mark.parametrize("kind",KINDS)
def test_each_comment_reaction_is_session_owned_idempotent_replaceable_and_removable(target_comment,kind):
    client,c,owner,comment_id,*_=target_comment
    path=f"/comments/{comment_id}/reactions"
    for _ in range(2):
        response=mutation(client,"PUT",path,{"reaction_type":kind,"user_id":str(uuid4())})
        assert response.status_code==200 and response.json()=={"comment_id":str(comment_id),"reaction_type":kind}
    before=c.execute(text("SELECT user_id,created_at,updated_at FROM comment_reactions")).one()
    assert before.user_id==owner
    assert mutation(client,"PUT",path,{"reaction_type":"fire"}).status_code==200
    assert c.scalar(text("SELECT count(*) FROM comment_reactions"))==1
    assert c.execute(text("SELECT created_at FROM comment_reactions")).scalar_one()==before.created_at
    for _ in range(2):assert mutation(client,"DELETE",path).status_code==204
    assert c.scalar(text("SELECT count(*) FROM comment_reactions"))==0
    for table in ("aura_ledger","wallet_transactions"):
        assert c.scalar(text("SELECT count(*) FROM "+table))==0

@pytest.mark.integration
def test_comment_guest_counts_private_viewer_and_active_actors_only(target_comment):
    client,c,owner,comment_id,*_=target_comment
    path=f"/comments/{comment_id}/reactions";read=f"/api/v1/comments/{comment_id}/interactions"
    assert mutation(client,"PUT",path,{"reaction_type":"love"}).status_code==200
    client.cookies.clear()
    dto=client.get(read).json()
    assert dto=={"comment_id":str(comment_id),"reaction_counts":{k:int(k=="love") for k in KINDS},"viewer_reaction":None}
    assert str(owner) not in str(dto)
    result=register(client,username="another_actor",email="actor@example.com");assert result.status_code==201
    second=UUID(result.json()["id"]);assert login(client,email="actor@example.com").status_code==200
    assert mutation(client,"PUT",path,{"reaction_type":"angry"}).status_code==200
    assert client.get(read).json()["viewer_reaction"]=="angry"
    # Removing the viewer never removes the first actor.
    assert mutation(client,"DELETE",path).status_code==204
    assert c.scalar(text("SELECT count(*) FROM comment_reactions WHERE user_id=:id"),{"id":owner})==1
    assert mutation(client,"PUT",path,{"reaction_type":"angry"}).status_code==200
    c.execute(text("UPDATE users SET status='locked' WHERE id=:id"),{"id":second})
    client.cookies.clear();assert client.get(read).json()["reaction_counts"]["angry"]==0

@pytest.mark.integration
@pytest.mark.parametrize("state",["comment_hidden","comment_deleted","post_hidden","post_deleted","category","author"])
def test_nonpublic_comment_refuses_reads_and_mutations(target_comment,state):
    client,c,owner,comment_id,post_id,category=target_comment
    if state.startswith("comment_"):
        deleted=state.endswith("deleted")
        c.execute(text("UPDATE comments SET status=:status,deleted_at="+("now()" if deleted else "NULL")+" WHERE id=:id"),
                  {"status":"deleted" if deleted else "hidden","id":comment_id})
    elif state.startswith("post_"):
        deleted=state.endswith("deleted")
        c.execute(text("UPDATE posts SET status=:status,deleted_at="+("now()" if deleted else "NULL")+" WHERE id=:id"),
                  {"status":"deleted" if deleted else "hidden","id":post_id})
    elif state=="category":c.execute(text("UPDATE categories SET status='hidden' WHERE id=:id"),{"id":category})
    else:
        # Use another active commenter so the acting session remains valid.
        client.cookies.clear();r=register(client,username="active_actor",email="active@example.com")
        assert r.status_code==201 and login(client,email="active@example.com").status_code==200
        c.execute(text("UPDATE users SET status='locked' WHERE id=:id"),{"id":owner})
    assert client.get(f"/api/v1/comments/{comment_id}/interactions").status_code==404
    for method in ("PUT","DELETE"):
        assert mutation(client,method,f"/comments/{comment_id}/reactions",{"reaction_type":"fire"} if method=="PUT" else None).status_code==404
    assert c.scalar(text("SELECT count(*) FROM comment_reactions"))==0

@pytest.mark.integration
def test_comment_reactions_require_session_csrf_and_valid_kind(target_comment):
    client,c,_,comment_id,*_=target_comment;path=f"/api/v1/comments/{comment_id}/reactions"
    assert client.put(path,json={"reaction_type":"love"},headers={"Origin":ORIGIN}).status_code==403
    assert mutation(client,"PUT",f"/comments/{comment_id}/reactions",{"reaction_type":"unknown"}).status_code==422
    assert mutation(client,"PUT",f"/comments/{comment_id}/reactions",{"reaction_type":"love"},origin="https://evil.example").status_code==403
    client.cookies.clear();assert client.put(path,json={"reaction_type":"fire"}).status_code==401
    assert c.scalar(text("SELECT count(*) FROM comment_reactions"))==0

@pytest.mark.integration
@pytest.mark.parametrize("kind",KINDS)
def test_all_six_post_reactions_have_real_counts(comments,kind):
    client,c,_,post_id,_=comments
    for _ in range(2):assert mutation(client,"PUT",f"/posts/{post_id}/reactions",{"reaction_type":kind}).status_code==200
    dto=client.get(f"/api/v1/posts/{post_id}/interactions").json()
    assert dto["reaction_counts"]=={k:int(k==kind) for k in KINDS}
    assert dto["viewer_reaction"]==kind
    assert c.scalar(text("SELECT count(*) FROM post_reactions"))==1

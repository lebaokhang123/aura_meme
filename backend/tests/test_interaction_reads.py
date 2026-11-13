"""Public counters and session-owned saved posts, without rewards or identity leaks."""
from uuid import UUID, uuid4

import pytest
from sqlalchemy import text

from test_auth import auth, migrated, login, register
from test_blog import blog, create_post, mutation
from test_interactions import target


def test_interaction_read_contract():
    from app.main import app
    contract = app.openapi()
    detail = contract["paths"]["/api/v1/posts/{post_id}/interactions"]["get"]
    assert detail["operationId"] == "getPostInteractions"
    assert {} in detail["security"] and {"sessionCookie": []} in detail["security"]
    fields = contract["components"]["schemas"]["PostInteractions"]["properties"]
    assert set(fields) == {"post_id", "reaction_counts", "comments_count", "viewer_reaction", "bookmarked"}
    saved = contract["paths"]["/api/v1/users/me/bookmarks"]["get"]
    assert saved["operationId"] == "listSavedPosts"
    assert saved["security"] == [{"sessionCookie": []}]
    assert {p["name"] for p in saved["parameters"]} == {"page", "page_size", "search", "category", "sort"}
    assert saved["responses"]["200"]["content"]["application/json"]["schema"]["$ref"].endswith("/PostPage")


@pytest.mark.integration
def test_counts_and_private_viewer_state_do_not_leak_to_guests(target):
    client, connection, owner, post_id, _ = target
    assert mutation(client, "PUT", f"/posts/{post_id}/reactions", {"reaction_type": "like"}).status_code == 200
    assert mutation(client, "PUT", f"/posts/{post_id}/bookmark").status_code == 204
    assert mutation(client, "POST", f"/posts/{post_id}/comments", {"body": "Visible comment"}).status_code == 201
    path = f"/api/v1/posts/{post_id}/interactions"
    expected = {"post_id": str(post_id), "reaction_counts": {"like": 1, "love": 0, "laugh": 0, "fire": 0, "sad": 0, "angry": 0},
                "comments_count": 1, "viewer_reaction": "like", "bookmarked": True}
    response = client.get(path)
    assert response.status_code == 200 and response.json() == expected
    assert "am_session=" in response.headers.get("set-cookie", "")
    client.cookies.clear()
    response = client.get(path)
    assert response.status_code == 200
    assert response.json() == expected | {"viewer_reaction": None, "bookmarked": False}
    assert "am_session=" not in response.headers.get("set-cookie", "")
    assert str(owner) not in response.text and "bookmark_count" not in response.text
    for table in ("aura_ledger", "wallet_transactions"):
        assert connection.scalar(text(f"SELECT count(*) FROM {table}")) == 0


@pytest.mark.integration
def test_other_viewer_gets_own_state_and_only_visible_active_actor_counts(target):
    client, connection, _, post_id, _ = target
    assert mutation(client, "PUT", f"/posts/{post_id}/bookmark").status_code == 204
    assert mutation(client, "POST", "/auth/logout").status_code == 204
    registered = register(client, username="reader_actor", email="reader@example.com")
    actor = UUID(registered.json()["id"])
    assert login(client, email="reader@example.com").status_code == 200
    assert mutation(client, "PUT", f"/posts/{post_id}/reactions", {"reaction_type": "fire"}).status_code == 200
    added = mutation(client, "POST", f"/posts/{post_id}/comments", {"body": "Actor comment"})
    assert added.status_code == 201
    path = f"/api/v1/posts/{post_id}/interactions"
    result = client.get(path).json()
    assert result["viewer_reaction"] == "fire" and result["bookmarked"] is False
    assert result["comments_count"] == 1 and result["reaction_counts"]["fire"] == 1
    connection.execute(text("UPDATE comments SET status='deleted',deleted_at=now() WHERE id=:id"),
                       {"id": UUID(added.json()["id"])})
    assert client.get(path).json()["comments_count"] == 0
    connection.execute(text("UPDATE users SET status='locked' WHERE id=:id"), {"id": actor})
    client.cookies.clear()
    result = client.get(path).json()
    assert result["reaction_counts"] == {"like": 0, "love": 0, "laugh": 0, "fire": 0, "sad": 0, "angry": 0}


@pytest.mark.integration
@pytest.mark.parametrize("state", ["draft", "hidden", "deleted", "category", "author", "media", "missing"])
def test_nonpublic_interaction_reads_do_not_reveal_counts(target, state):
    client, connection, owner, post_id, category = target
    if state in {"draft", "hidden", "deleted"}:
        connection.execute(text("UPDATE posts SET status=:state,deleted_at=CASE WHEN :state='deleted' THEN now() ELSE NULL END WHERE id=:id"), {"state": state, "id": post_id})
    elif state == "category":
        connection.execute(text("UPDATE categories SET status='hidden' WHERE id=:id"), {"id": category})
    elif state == "author":
        connection.execute(text("UPDATE users SET status='locked' WHERE id=:id"), {"id": owner})
    elif state == "media":
        media = uuid4()
        connection.execute(text("INSERT INTO media_uploads(id,owner_id,object_key,mime,size_bytes,status,created_at,updated_at) VALUES(:id,:owner,:key,'image/png',1,'pending',now(),now())"), {"id": media, "owner": owner, "key": media.hex})
        connection.execute(text("UPDATE posts SET media_id=:media WHERE id=:id"), {"media": media, "id": post_id})
    else:
        post_id = uuid4()
    client.cookies.clear()
    assert client.get(f"/api/v1/posts/{post_id}/interactions").status_code == 404


@pytest.mark.integration
@pytest.mark.parametrize("path", ["/posts/{post_id}/interactions", "/users/me/bookmarks"])
@pytest.mark.parametrize("value", ["invalid", ""])
def test_invalid_cookie_is_never_silently_downgraded_to_guest(target, path, value):
    client, _, _, post_id, _ = target
    client.cookies.clear()
    client.cookies.set("am_session", value)
    assert client.get("/api/v1" + path.format(post_id=post_id)).status_code == 401


@pytest.mark.integration
def test_saved_feed_filters_pages_and_never_exposes_another_users_saves(blog):
    client, connection, _, _, _ = blog
    saved_ids = []
    for title in ("Zulu", "Alpha 100%", "Beta"):
        post = create_post(blog, title=title, status="published")
        assert post.status_code == 201
        post_id = post.json()["id"]
        saved_ids.append(post_id)
        assert mutation(client, "PUT", f"/posts/{post_id}/bookmark").status_code == 204
    path = "/api/v1/users/me/bookmarks"
    result = client.get(path + "?sort=title_asc&page_size=1&page=2").json()
    assert result["pagination"] == {"page": 2, "page_size": 1, "total": 3, "total_pages": 3}
    assert result["items"][0]["title"] == "Beta"
    assert client.get(path + "?search=%25").json()["pagination"]["total"] == 1
    assert client.get(path + "?category=no-such-category").json()["items"] == []
    assert client.get(path + "?page=" + "9" * 30).json()["items"] == []
    connection.execute(text("UPDATE posts SET status='hidden' WHERE id=:id"), {"id": UUID(saved_ids[0])})
    assert client.get(path).json()["pagination"]["total"] == 2
    assert mutation(client, "POST", "/auth/logout").status_code == 204
    assert register(client, username="other_reader", email="other-reader@example.com").status_code == 201
    assert login(client, email="other-reader@example.com").status_code == 200
    assert client.get(path).json()["items"] == []
    client.cookies.clear()
    assert client.get(path).status_code == 401


@pytest.mark.integration
@pytest.mark.parametrize("query", ["page=0", "page_size=101", "sort=arbitrary_sql", "search=%00", "search=" + "x" * 101])
def test_saved_query_validation(target, query):
    assert target[0].get("/api/v1/users/me/bookmarks?" + query).status_code == 422

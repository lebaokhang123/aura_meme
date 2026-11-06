"""Reaction/bookmark mechanics never issue rewards or trust a client actor ID."""
from uuid import UUID, uuid4

import pytest
from sqlalchemy import text

from test_auth import auth, migrated, ORIGIN, csrf, login, register
from test_blog import blog, create_post, mutation


@pytest.fixture
def target(blog):
    client, connection, owner, category, _ = blog
    response = create_post(blog, status="published")
    assert response.status_code == 201
    return client, connection, owner, UUID(response.json()["id"]), category


@pytest.mark.integration
def test_reaction_replace_retry_and_remove(target):
    client, connection, owner, post_id, _ = target
    path = f"/posts/{post_id}/reactions"
    for kind in ("like", "like", "fire", "laugh"):
        response = mutation(client, "PUT", path, {"reaction_type": kind})
        assert response.status_code == 200, response.text
        assert response.json() == {"reaction_type": kind, "post_id": str(post_id)}
        row = connection.execute(text("SELECT * FROM post_reactions")).mappings().one()
        assert row["user_id"] == owner and row["reaction_type"] == kind
    assert mutation(client, "DELETE", path).status_code == 204
    assert mutation(client, "DELETE", path).status_code == 204
    assert connection.scalar(text("SELECT count(*) FROM post_reactions")) == 0


@pytest.mark.integration
def test_bookmark_retry_and_remove(target):
    client, connection, owner, post_id, _ = target
    path = f"/posts/{post_id}/bookmark"
    for _ in range(2):
        assert mutation(client, "PUT", path).status_code == 204
        row = connection.execute(text("SELECT * FROM post_bookmarks")).mappings().one()
        assert row["user_id"] == owner
    assert mutation(client, "DELETE", path).status_code == 204
    assert mutation(client, "DELETE", path).status_code == 204
    assert connection.scalar(text("SELECT count(*) FROM post_bookmarks")) == 0


@pytest.mark.integration
@pytest.mark.parametrize("suffix", ["reactions", "bookmark"])
@pytest.mark.parametrize("state", ["draft", "hidden", "deleted", "category", "missing", "author_locked", "author_deleted", "media"])
def test_nonpublic_target_refuses_interactions(target, suffix, state):
    client, connection, owner, post_id, category = target
    if state in {"draft", "hidden", "deleted"}:
        connection.execute(text("UPDATE posts SET status=:status, deleted_at=CASE WHEN :status='deleted' THEN now() ELSE NULL END WHERE id=:id"), {"status": state, "id": post_id})
    elif state == "category":
        connection.execute(text("UPDATE categories SET status='hidden' WHERE id=:id"), {"id": category})
    elif state.startswith("author_"):
        assert mutation(client, "POST", "/auth/logout").status_code == 204
        assert register(client, username="visible_actor", email="visible-actor@example.com").status_code == 201
        assert login(client, email="visible-actor@example.com").status_code == 200
        connection.execute(text("UPDATE users SET status=:status,deleted_at=CASE WHEN :status='deleted' THEN now() ELSE NULL END WHERE id=:id"), {"status": state.removeprefix("author_"), "id": owner})
    elif state == "media":
        media = uuid4()
        connection.execute(text("INSERT INTO media_uploads (id,owner_id,object_key,mime,size_bytes,status,created_at,updated_at) VALUES (:id,:owner,:key,'image/png',1,'pending',now(),now())"), {"id": media, "owner": owner, "key": media.hex})
        connection.execute(text("UPDATE posts SET media_id=:media WHERE id=:id"), {"media": media, "id": post_id})
    else:
        post_id = uuid4()
    for method in ("PUT", "DELETE"):
        assert mutation(client, method, f"/posts/{post_id}/{suffix}", {"reaction_type": "like"}).status_code == 404


@pytest.mark.integration
@pytest.mark.parametrize("suffix", ["reactions", "bookmark"])
@pytest.mark.parametrize("method", ["PUT", "DELETE"])
def test_interactions_require_session_and_csrf(target, suffix, method):
    client, _, _, post_id, _ = target
    path = f"/api/v1/posts/{post_id}/{suffix}"
    assert client.request(method, path, json={"reaction_type": "like"}, headers={"Origin": ORIGIN}).status_code == 403
    client.cookies.clear()
    assert client.request(method, path, json={"reaction_type": "like"}, headers={"Origin": ORIGIN}).status_code == 401


@pytest.mark.integration
@pytest.mark.parametrize("value", ["unknown", "LIKE", "", None, 1, []])
def test_invalid_reaction_does_not_write(target, value):
    client, connection, _, post_id, _ = target
    assert mutation(client, "PUT", f"/posts/{post_id}/reactions", {"reaction_type": value}).status_code == 422
    assert connection.scalar(text("SELECT count(*) FROM post_reactions")) == 0


@pytest.mark.integration
def test_contract_extra_fields_never_override_actor_or_post(target):
    client, connection, owner, post_id, _ = target
    # Existing ReactionInput permits extra properties; they are ignored, never persisted.
    response = mutation(client, "PUT", f"/posts/{post_id}/reactions", {
        "reaction_type": "like", "user_id": str(uuid4()), "post_id": str(uuid4()), "xp": 999999,
    })
    assert response.status_code == 200
    assert connection.execute(text("SELECT user_id,post_id FROM post_reactions")).one() == (owner, post_id)
    assert set(response.json()) == {"reaction_type", "post_id"}


@pytest.mark.integration
@pytest.mark.parametrize("suffix,table", [("reactions", "post_reactions"), ("bookmark", "post_bookmarks")])
def test_another_user_cannot_replace_or_remove_owners_interaction(target, suffix, table):
    client, connection, owner, post_id, _ = target
    path = f"/posts/{post_id}/{suffix}"
    assert mutation(client, "PUT", path, {"reaction_type": "like"}).status_code in {200, 204}
    assert mutation(client, "POST", "/auth/logout").status_code == 204
    assert register(client, username="another_actor", email="another-actor@example.com").status_code == 201
    assert login(client, email="another-actor@example.com").status_code == 200
    assert mutation(client, "PUT", path, {"reaction_type": "fire"}).status_code in {200, 204}
    assert connection.scalar(text('SELECT count(*) FROM "' + table + '"')) == 2
    assert mutation(client, "DELETE", path).status_code == 204
    assert connection.execute(text('SELECT user_id FROM "' + table + '"')).one() == (owner,)


@pytest.mark.integration
@pytest.mark.parametrize("suffix", ["reactions", "bookmark"])
def test_failed_database_mutation_rolls_back_and_hides_driver_details(target, suffix):
    client, connection, _, post_id, _ = target
    table = "post_reactions" if suffix == "reactions" else "post_bookmarks"
    connection.exec_driver_sql("CREATE FUNCTION m61a_reject() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'synthetic interaction failure'; END $$")
    connection.exec_driver_sql(f"CREATE TRIGGER m61a_reject BEFORE INSERT ON {table} FOR EACH ROW EXECUTE FUNCTION m61a_reject()")
    response = mutation(client, "PUT", f"/posts/{post_id}/{suffix}", {"reaction_type": "like"})
    assert response.status_code == 500 and "synthetic" not in response.text
    assert connection.scalar(text('SELECT count(*) FROM "' + table + '"')) == 0


@pytest.mark.integration
def test_reaction_check_and_composite_pk_are_enforced(target):
    from sqlalchemy.exc import IntegrityError
    client, connection, owner, post_id, _ = target
    values = {"post": post_id, "user": owner, "kind": "invalid"}
    sql = text("INSERT INTO post_reactions VALUES (:post,:user,:kind,now(),now())")
    with pytest.raises(IntegrityError) as fault, connection.begin_nested():
        connection.execute(sql, values)
    assert fault.value.orig.diag.constraint_name == "ck_post_reactions_reaction_type"
    values["kind"] = "fire"
    connection.execute(sql, values)
    with pytest.raises(IntegrityError) as fault, connection.begin_nested():
        connection.execute(sql, values)
    assert fault.value.orig.diag.constraint_name == "pk_post_reactions"


def test_interaction_openapi_matches_existing_contract():
    from app.main import app
    contract = app.openapi()
    for suffix, operations in [("reactions", ("setReaction", "removeReaction")), ("bookmark", ("savePost", "unsavePost"))]:
        paths = contract["paths"]["/api/v1/posts/{post_id}/" + suffix]
        assert set(paths) == {"put", "delete"}
        for method, operation in zip(("put", "delete"), operations):
            item = paths[method]
            assert item["operationId"] == operation and item["security"] == [{"sessionCookie": []}]
            assert {"401", "403", "404", "409", "422", "429", "500"} <= set(item["responses"])
    assert contract["components"]["schemas"]["ReactionInput"]["properties"]["reaction_type"]["enum"] == ["like", "laugh", "fire"]

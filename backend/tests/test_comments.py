"""P0 comments through the real API and rollback-only PostgreSQL fixture."""
from datetime import timedelta
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select, text

from app.comments import CommentInput
from app.models import AuthSession, Category, Comment, MediaUpload, Post, Profile, User
from test_auth import ORIGIN, auth, csrf, login, migrated, register
from test_blog import blog, create_post, mutation


@pytest.fixture
def comments(blog):
    client, connection, owner, category, hidden = blog
    response = create_post(blog, status="published")
    assert response.status_code == 201
    return client, connection, owner, UUID(response.json()["id"]), category


def add(client, target_post, **values):
    return mutation(client, "POST", f"/posts/{target_post}/comments", {"body": "A comment"} | values)


def listing(client, post_id, query=""):
    return client.get(f"/api/v1/posts/{post_id}/comments" + query)


@pytest.mark.integration
def test_create_comment_text_and_public_whitelist(comments):
    client, connection, owner, post_id, _ = comments
    body = "  <script>alert('text only')</script>\nBình luận 🐱  "
    response = add(client, post_id, body=body)
    assert response.status_code == 201, response.text
    dto = response.json()
    assert set(dto) == {"id", "post_id", "author", "body", "created_at"}
    assert dto["body"] == body and dto["post_id"] == str(post_id)
    assert set(dto["author"]) == {"id", "username", "display_name", "created_at", "bio", "avatar_url"}
    assert dto["author"]["id"] == str(owner)
    row = connection.execute(select(Comment.__table__)).mappings().one()
    assert row["status"] == "visible" and row["deleted_at"] is None
    assert row["created_at"] == row["updated_at"]
    client.cookies.clear()
    assert listing(client, post_id).json()["items"] == [dto]


@pytest.mark.integration
@pytest.mark.parametrize("body", ["", " \n\t", "x" * 4001, 1, None, {}, [], "\x00", "\ud800"])
def test_invalid_body_does_not_insert(comments, body):
    client, connection, _, post_id, _ = comments
    # ASCII JSON escapes allow malformed Unicode to reach the runtime validator.
    import json
    response = client.post(f"/api/v1/posts/{post_id}/comments", content=json.dumps({"body": body}),
        headers={"Content-Type": "application/json", "Origin": ORIGIN, "X-CSRF-Token": csrf(client)})
    assert response.status_code == 422
    assert connection.execute(select(Comment.id)).all() == []


@pytest.mark.integration
@pytest.mark.parametrize("field", ["author_id", "post_id", "status", "roles", "unexpected"])
def test_comment_input_rejects_forged_fields(comments, field):
    client, connection, _, post_id, _ = comments
    assert add(client, post_id, **{field: "forged"}).status_code == 422
    assert connection.execute(select(Comment.id)).all() == []


@pytest.mark.integration
@pytest.mark.parametrize("reason", ["draft", "hidden", "deleted", "category", "author_locked", "author_deleted", "media", "missing"])
def test_nonpublic_post_has_no_comment_access(comments, reason):
    client, connection, owner, post_id, category = comments
    assert add(client, post_id).status_code == 201
    now = client.app.state.auth.now()
    if reason in {"draft", "hidden", "deleted"}:
        connection.execute(Post.__table__.update().where(Post.id == post_id).values(status=reason, deleted_at=now if reason == "deleted" else None))
    elif reason == "category":
        connection.execute(Category.__table__.update().where(Category.id == category).values(status="hidden"))
    elif reason.startswith("author_"):
        # Distinct authenticated commenter avoids mixing post visibility with blocked-session 401.
        assert mutation(client, "POST", "/auth/logout").status_code == 204
        assert register(client, username="second_comment", email="second-comment@example.com").status_code == 201
        assert login(client, email="second-comment@example.com").status_code == 200
        connection.execute(User.__table__.update().where(User.id == owner).values(
            status=reason.removeprefix("author_"), deleted_at=now if reason == "author_deleted" else None))
    elif reason == "media":
        media = uuid4()
        connection.execute(MediaUpload.__table__.insert().values(id=media, owner_id=owner, object_key="synthetic-comment-media", mime="image/png", size_bytes=1, status="pending", created_at=now, updated_at=now))
        connection.execute(Post.__table__.update().where(Post.id == post_id).values(media_id=media))
    else:
        post_id = uuid4()
    assert listing(client, post_id).status_code == 404
    assert add(client, post_id).status_code == 404
    assert len(connection.execute(select(Comment.id)).all()) == 1


@pytest.mark.integration
def test_pagination_visibility_stable_sort_and_no_n_plus_one(comments):
    from sqlalchemy import event
    client, connection, owner, post_id, _ = comments
    now = client.app.state.auth.now()
    ids = [UUID(int=index + 1) for index in range(25)]
    rows = [dict(id=ident, post_id=post_id, author_id=owner, body="row", status="visible",
                 created_at=now, updated_at=now) for ident in ids]
    connection.execute(Comment.__table__.insert(), rows)
    connection.execute(Comment.__table__.update().where(Comment.id == ids[-1]).values(status="hidden"))
    connection.execute(Comment.__table__.update().where(Comment.id == ids[-2]).values(status="deleted", deleted_at=now))
    queries = []
    def record(conn, cursor, statement, parameters, context, executemany):
        if statement.lstrip().upper().startswith("SELECT"):
            queries.append(statement)
    event.listen(connection, "before_cursor_execute", record)
    try:
        first = listing(client, post_id).json()
        assert len(queries) == 3  # One post lookup, one filtered count and one joined page, independent of size.
    finally:
        event.remove(connection, "before_cursor_execute", record)
    assert first["pagination"] == dict(page=1, page_size=20, total=23, total_pages=2)
    assert [item["id"] for item in first["items"]] == [str(ident) for ident in ids[:20]]
    second = listing(client, post_id, "?page=2").json()
    assert [item["id"] for item in second["items"]] == [str(ident) for ident in ids[20:23]]
    for page in (3, 10**40):
        response = listing(client, post_id, f"?page={page}").json()
        assert response["items"] == [] and response["pagination"]["total"] == 23
    assert listing(client, post_id, "?page_size=100").json()["pagination"]["total"] == 23


@pytest.mark.integration
@pytest.mark.parametrize("query", ["?page=0", "?page_size=0", "?page_size=101", "?page=bad"])
def test_pagination_bounds(comments, query):
    client, _, _, post_id, _ = comments
    assert listing(client, post_id, query).status_code == 422


@pytest.mark.integration
@pytest.mark.parametrize("status", ["locked", "deleted"])
def test_comment_author_must_be_public(comments, status):
    client, connection, owner, post_id, _ = comments
    assert mutation(client, "POST", "/auth/logout").status_code == 204
    other = register(client, username="comment_author", email="comment-author@example.com").json()
    assert login(client, email="comment-author@example.com").status_code == 200
    assert add(client, post_id).status_code == 201
    connection.execute(User.__table__.update().where(User.id == UUID(other["id"])).values(
        status=status, deleted_at=client.app.state.auth.now() if status == "deleted" else None))
    response = listing(client, post_id).json()
    assert response["items"] == [] and response["pagination"]["total"] == 0


@pytest.mark.integration
@pytest.mark.parametrize("hidden", [False, True])
def test_owner_soft_delete_and_repeated_delete(comments, hidden):
    client, connection, owner, post_id, _ = comments
    ident = UUID(add(client, post_id).json()["id"])
    if hidden: connection.execute(Comment.__table__.update().where(Comment.id == ident).values(status="hidden"))
    before = connection.execute(select(Comment.__table__)).mappings().one()
    response = mutation(client, "DELETE", "/comments/" + str(ident))
    assert response.status_code == 204 and response.content == b""
    after = dict(connection.execute(select(Comment.__table__)).mappings().one())
    assert after["status"] == "deleted" and after["deleted_at"] == after["updated_at"]
    assert all(after[field] == before[field] for field in ["id", "post_id", "author_id", "body", "created_at"])
    assert listing(client, post_id).json()["pagination"]["total"] == 0
    client.app.state.auth.now = lambda: after["deleted_at"] + timedelta(minutes=1)
    assert mutation(client, "DELETE", "/comments/" + str(ident)).status_code == 404
    assert dict(connection.execute(select(Comment.__table__)).mappings().one()) == after


@pytest.mark.integration
def test_other_user_cannot_delete_owner_comment(comments):
    client, connection, owner, post_id, _ = comments
    ident = add(client, post_id).json()["id"]
    assert mutation(client, "POST", "/auth/logout").status_code == 204
    assert register(client, username="foreign_comment", email="foreign-comment@example.com").status_code == 201
    assert login(client, email="foreign-comment@example.com").status_code == 200
    assert mutation(client, "DELETE", "/comments/" + ident).status_code == 404
    assert mutation(client, "DELETE", "/comments/" + str(uuid4())).status_code == 404
    assert connection.scalar(select(Comment.status)) == "visible"


@pytest.mark.integration
@pytest.mark.parametrize("method", ["POST", "DELETE"])
@pytest.mark.parametrize("problem", ["anonymous", "csrf", "origin", "revoked", "expired"])
def test_comment_mutation_auth_security(comments, method, problem):
    client, connection, _, post_id, _ = comments
    ident = add(client, post_id).json()["id"]
    token = csrf(client)
    if problem == "anonymous": client.cookies.clear()
    if problem == "revoked":
        connection.execute(AuthSession.__table__.update().values(revoked_at=client.app.state.auth.now()))
    if problem == "expired":
        now = client.app.state.auth.now()
        connection.execute(AuthSession.__table__.update().values(created_at=now - timedelta(hours=1), expires_at=now - timedelta(seconds=1)))
    path = f"/posts/{post_id}/comments" if method == "POST" else "/comments/" + ident
    response = mutation(client, method, path, {"body": "new"} if method == "POST" else None,
                        token="bad" if problem == "csrf" else token,
                        origin="https://evil.example" if problem == "origin" else ORIGIN)
    assert response.status_code == (403 if problem in {"csrf", "origin"} else 401)
    assert connection.execute(select(Comment.status)).scalars().all() == ["visible"]


@pytest.mark.integration
def test_uuid_boundaries_max_length_and_no_patch(comments):
    client, connection, _, post_id, _ = comments
    assert listing(client, "bad-uuid").status_code == 422
    assert add(client, "bad-uuid").status_code == 422
    assert mutation(client, "DELETE", "/comments/bad-uuid").status_code == 422
    dto = add(client, post_id, body="🐱" * 4000).json()
    assert len(dto["body"]) == 4000
    assert client.patch("/api/v1/comments/" + dto["id"], json={"body": "changed"}).status_code == 405
    from sqlalchemy.exc import IntegrityError
    with pytest.raises(IntegrityError) as error, connection.begin_nested():
        connection.execute(Comment.__table__.update().where(Comment.id == UUID(dto["id"])).values(status="deleted"))
    assert error.value.orig.diag.constraint_name == "ck_comments_deleted_at"


@pytest.mark.integration
@pytest.mark.parametrize("action", ["insert", "delete"])
def test_comment_transaction_failure_rolls_back(comments, action):
    client, connection, _, post_id, _ = comments
    ident = add(client, post_id).json()["id"]
    before = dict(connection.execute(select(Comment.__table__)).mappings().one())
    connection.exec_driver_sql("CREATE FUNCTION m33_reject_comment() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'synthetic comment failure'; END $$")
    event = "INSERT" if action == "insert" else "UPDATE"
    connection.exec_driver_sql(f"CREATE TRIGGER m33_reject_comment BEFORE {event} ON comments FOR EACH ROW EXECUTE FUNCTION m33_reject_comment()")
    response = add(client, post_id) if action == "insert" else mutation(client, "DELETE", "/comments/" + ident)
    assert response.status_code == 500 and "synthetic" not in response.text
    assert dict(connection.execute(select(Comment.__table__)).mappings().one()) == before


def test_comment_openapi_contract():
    from app.main import app
    contract = app.openapi()
    nested = contract["paths"]["/api/v1/posts/{post_id}/comments"]
    assert set(nested) == {"get", "post"}
    assert not nested["get"].get("security")
    assert nested["post"]["security"] == [{"sessionCookie": []}]
    delete = contract["paths"]["/api/v1/comments/{comment_id}"]
    assert set(delete) == {"delete"}
    assert delete["delete"]["operationId"] == "deleteComment"
    assert "204" in delete["delete"]["responses"]
    assert nested["get"]["operationId"] == "listComments" and nested["post"]["operationId"] == "addComment"
    assert {item["name"] for item in nested["get"]["parameters"]} == {"post_id", "page", "page_size", "search", "sort", "author"}
    for operation in [nested["post"], delete["delete"]]:
        assert {"name": "X-CSRF-Token", "in": "header", "required": True, "schema": {"type": "string"}} in operation["parameters"]
        assert {"401", "403", "404", "422", "429", "500"} <= set(operation["responses"])
    schema = contract["components"]["schemas"]["CommentInput"]
    assert schema["additionalProperties"] is False and schema["required"] == ["body"]
    assert schema["properties"]["body"]["minLength"] == 1 and schema["properties"]["body"]["maxLength"] == 4000


@pytest.mark.integration
def test_delete_boundary_reuses_https_and_limiter(comments):
    from fastapi.testclient import TestClient
    from app.main import app
    client, _, _, post_id, _ = comments
    insecure = TestClient(app, base_url="http://testserver")
    try:
        assert insecure.delete("/api/v1/comments/" + str(uuid4())).status_code == 403
    finally:
        insecure.close()
    client.cookies.clear()
    path = "/api/v1/comments/" + str(uuid4())
    statuses = [client.delete(path).status_code for _ in range(61)]
    assert statuses[:60] == [401] * 60 and statuses[-1] == 429

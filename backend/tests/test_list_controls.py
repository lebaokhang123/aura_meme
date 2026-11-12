"""Assignment-wide list search, filtering and stable sort controls."""
import pytest
from sqlalchemy import text

from test_auth import auth, migrated, PASSWORD
from test_blog import admin, blog, create_post, mutation
from test_contact import send


@pytest.mark.parametrize("length,accepted", [(80, True), (81, False)])
def test_category_input_slug_v1_boundary(length, accepted):
    from pydantic import ValidationError
    from app.blog_schemas import CategoryInput
    if accepted:
        assert CategoryInput(name="Boundary", slug="a" * length).slug == "a" * length
    else:
        with pytest.raises(ValidationError):
            CategoryInput(name="Boundary", slug="a" * length)
    assert CategoryInput.model_json_schema()["properties"]["slug"]["maxLength"] == 80


@pytest.mark.integration
@pytest.mark.parametrize("length,status", [(80, 201), (81, 422)])
def test_category_create_slug_v1_boundary(admin, length, status):
    response = mutation(admin[0], "POST", "/admin/categories", {"name": "Boundary", "slug": "a" * length})
    assert response.status_code == status
    if status == 201:
        found = admin[0].get("/api/v1/categories", params={"slug": "a" * length})
        assert found.json()["items"][0]["slug"] == "a" * length


@pytest.mark.parametrize("path,required", [
    ("/api/v1/users/me/posts", {"search", "category", "sort", "status"}),
    ("/api/v1/admin/users", {"search", "sort", "status", "role"}),
    ("/api/v1/admin/posts", {"search", "sort", "status", "category"}),
    ("/api/v1/admin/categories", {"search", "sort", "status"}),
    ("/api/v1/admin/contacts", {"search", "sort", "status"}),
    ("/api/v1/admin/audit-logs", {"search", "sort", "action", "target_type", "actor_id"}),
    ("/api/v1/categories", {"search", "sort", "slug"}),
])
def test_all_assignment_lists_have_query_controls(path, required):
    from app.main import app
    operation = app.openapi()["paths"][path]["get"]
    assert required | {"page", "page_size"} <= {field["name"] for field in operation["parameters"]}


@pytest.mark.integration
@pytest.mark.parametrize("path", ["/posts", "/users/me/posts", "/admin/users", "/admin/posts", "/admin/categories", "/admin/contacts", "/admin/audit-logs", "/categories"])
def test_unknown_sort_and_invalid_query_are_rejected(admin, path):
    client = admin[0]
    for query in ("sort=DROP_TABLE", "search=%00", "search=" + "x" * 101):
        assert client.get("/api/v1" + path + "?" + query).status_code == 422


@pytest.mark.parametrize("parameter", ["search", "category"])
def test_public_post_nul_is_rejected_before_database_access(parameter):
    from app.blog import list_posts
    from app.security import AuthError
    values = {"search": None, "category": None, parameter: "\x00"}
    with pytest.raises(AuthError) as failure:
        list_posts(None, page=1, page_size=20, sort="created_desc", **values)
    assert failure.value.status == 422


@pytest.mark.integration
def test_own_and_admin_posts_search_category_sort_and_page(admin):
    client, _, _, category, _ = admin
    for title in ("Zulu", "Alpha 100%", "Beta"):
        assert create_post(admin, title=title, status="published").status_code == 201
    assert create_post(admin, title="Draft", status="draft").status_code == 201
    for path in ("/users/me/posts", "/admin/posts"):
        result = client.get("/api/v1" + path + "?sort=title_asc&status=published&page_size=1&page=2").json()
        assert result["pagination"]["total"] == 3 and result["items"][0]["title"] == "Beta"
        assert client.get("/api/v1" + path + "?search=%25").json()["pagination"]["total"] == 1
        assert client.get("/api/v1" + path + "?category=absent").json()["items"] == []
        assert client.get("/api/v1" + path + "?category=active-cat").json()["pagination"]["total"] == 4


@pytest.mark.integration
def test_category_name_sort_search_and_public_filter(admin):
    client = admin[0]
    for name, slug in (("Zulu", "aaa"), ("Alpha", "zzz")):
        assert mutation(client, "POST", "/admin/categories", {"name": name, "slug": slug}).status_code == 201
    for path in ("/categories", "/admin/categories"):
        result = client.get("/api/v1" + path + "?sort=name_desc&search=lu").json()
        assert [row["name"] for row in result["items"]] == ["Zulu"]
    assert client.get("/api/v1/categories?slug=zzz").json()["items"][0]["name"] == "Alpha"
    assert client.get("/api/v1/categories?slug=hidden-cat").json()["items"] == []
    assert client.get("/api/v1/admin/categories?status=hidden").json()["pagination"]["total"] == 1


@pytest.mark.integration
def test_admin_users_role_filter_and_sort(admin):
    client = admin[0]
    added = mutation(client, "POST", "/admin/users", {"username": "zz_reader", "email": "zz@example.com", "display_name": "Zed", "password": PASSWORD, "roles": ["USER"]})
    assert added.status_code == 201
    result = client.get("/api/v1/admin/users?sort=username_desc&page_size=1").json()
    assert result["items"][0]["username"] == "zz_reader"
    only_admin = client.get("/api/v1/admin/users?role=ADMIN").json()
    assert only_admin["pagination"]["total"] == 1 and "ADMIN" in only_admin["items"][0]["roles"]
    assert client.get("/api/v1/admin/users?search=Zed").json()["pagination"]["total"] == 1


@pytest.mark.integration
def test_contact_search_and_audit_metadata_filter_do_not_search_private_snapshots(admin):
    client, connection, actor, *_ = admin
    for subject, body in (("Zulu", "Synthetic secret target"), ("Alpha", "Other body")):
        assert send(client, subject=subject, body=body).status_code == 201
    result = client.get("/api/v1/admin/contacts?sort=subject_asc&page_size=1").json()
    assert result["items"][0]["subject"] == "Alpha" and result["pagination"]["total"] == 2
    assert client.get("/api/v1/admin/contacts?search=secret&status=new").json()["pagination"]["total"] == 1
    contact_id = result["items"][0]["id"]
    assert mutation(client, "PATCH", "/admin/contacts/" + contact_id, {"status": "resolved"}).status_code == 200
    connection.execute(text("UPDATE admin_audit_logs SET after_json=jsonb_build_object('private','needle-only-snapshot')"))
    path = "/api/v1/admin/audit-logs"
    result = client.get(path + "?target_type=contact&sort=action_asc&actor_id=" + str(actor)).json()
    assert result["pagination"]["total"] == 1
    assert all(set(row) == {"id", "actor_id", "action", "target_type", "target_id", "created_at"} for row in result["items"])
    action = result["items"][0]["action"]
    assert client.get(path + "?action=" + action).json()["pagination"]["total"] == 1
    assert client.get(path + "?search=needle-only-snapshot").json()["items"] == []
    assert client.get(path + "?search=" + contact_id).json()["pagination"]["total"] == 1

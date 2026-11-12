"""Public comment list controls preserve visibility and stable pagination."""
import pytest

from test_auth import auth, migrated, login, register
from test_blog import blog, create_post, mutation


def test_public_comments_query_contract():
    from app.main import app
    operation = app.openapi()["paths"]["/api/v1/posts/{post_id}/comments"]["get"]
    parameters = {item["name"]: item["schema"] for item in operation["parameters"]}
    assert {"search", "sort", "author", "page", "page_size"} <= parameters.keys()
    assert parameters["sort"]["enum"] == ["created_asc", "created_desc"]
    assert parameters["sort"]["default"] == "created_asc"
    assert not operation.get("security")


@pytest.mark.integration
def test_public_comments_search_author_sort_and_pagination(blog):
    client = blog[0]
    post = create_post(blog, status="published").json()
    path = "/posts/" + post["id"] + "/comments"
    owner_ids = []
    for body in ("Zulu 100%", "Alpha", "Gamma"):
        added = mutation(client, "POST", path, {"body": body})
        assert added.status_code == 201
        owner_ids.append(added.json()["id"])
    assert mutation(client, "POST", "/auth/logout").status_code == 204
    assert register(client, username="comment_reader", email="comment-reader@example.com").status_code == 201
    assert login(client, email="comment-reader@example.com").status_code == 200
    other = mutation(client, "POST", path, {"body": "Beta"})
    assert other.status_code == 201
    all_ids = owner_ids + [other.json()["id"]]
    client.cookies.clear()
    response = client.get("/api/v1" + path + "?sort=created_desc&page_size=2&page=2")
    assert response.status_code == 200
    assert [row["id"] for row in response.json()["items"]] == sorted(all_ids, reverse=True)[2:]
    assert response.json()["pagination"]["total"] == 4
    expected = sorted(owner_ids)
    result = client.get("/api/v1" + path + "?author=alice_auth").json()
    assert [row["id"] for row in result["items"]] == expected
    assert client.get("/api/v1" + path + "?search=%25").json()["pagination"]["total"] == 1
    assert client.get("/api/v1" + path + "?author=absent").json()["items"] == []
    assert client.get("/api/v1" + path + "?page=" + "9" * 30).json()["items"] == []


@pytest.mark.integration
@pytest.mark.parametrize("query", ["search=%00", "sort=unsafe", "author=%00", "search=" + "x" * 101])
def test_invalid_comment_controls_rejected(blog, query):
    client = blog[0]
    post_id = create_post(blog, status="published").json()["id"]
    assert client.get(f"/api/v1/posts/{post_id}/comments?" + query).status_code == 422

import pytest
from fastapi.testclient import TestClient

from app.config import ConfigurationError
from app.main import app


def test_health_and_openapi_without_a_database(monkeypatch):
    monkeypatch.setenv("AUTH_SIGNING_KEY", "test-only-signing-key-with-at-least-32-bytes")
    monkeypatch.setenv(
        "DATABASE_URL", "postgresql+psycopg://test:not-a-real-secret@127.0.0.1:1/test"
    )
    with TestClient(app) as client:
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}
        assert client.app.state.engine.pool.checkedout() == 0
        schema = client.get("/openapi.json")
        assert schema.status_code == 200
        contract = schema.json()
        assert set(contract["paths"]) == {"/health", "/api/v1/auth/csrf", "/api/v1/auth/register",
                                          "/api/v1/auth/login", "/api/v1/auth/logout", "/api/v1/users/me",
                                          "/api/v1/users/me/password", "/api/v1/users/{username}", "/api/v1/categories",
                                          "/api/v1/admin/categories", "/api/v1/admin/categories/{category_id}",
                                          "/api/v1/posts", "/api/v1/posts/{post_id}", "/api/v1/media",
                                          "/api/v1/posts/{post_id}/comments", "/api/v1/comments/{comment_id}",
                                          "/api/v1/admin/users", "/api/v1/admin/users/{user_id}",
                                          "/api/v1/admin/users/{user_id}/roles", "/api/v1/admin/posts",
                                          "/api/v1/admin/posts/{post_id}", "/api/v1/admin/audit-logs", "/api/v1/contact",
                                          "/api/v1/admin/contacts", "/api/v1/admin/contacts/{contact_id}",
                                          "/api/v1/users/me/posts", "/api/v1/users/me/posts/{post_id}",
                                          "/api/v1/posts/{post_id}/reactions", "/api/v1/posts/{post_id}/bookmark"}
        assert contract["paths"]["/health"]["get"]["operationId"] == "health"
        model = contract["components"]["schemas"]["HealthResponse"]
        assert model["required"] == ["status"]
        assert model["properties"]["status"]["const"] == "ok"
        assert "not-a-real-secret" not in schema.text
        for path in ["register", "login", "logout"]:
            operation = contract["paths"]["/api/v1/auth/" + path]["post"]
            assert {"name": "X-CSRF-Token", "in": "header", "required": True,
                    "schema": {"type": "string"}} in operation["parameters"]
            assert "403" in operation["responses"]
        assert "401" in contract["paths"]["/api/v1/auth/login"]["post"]["responses"]
        assert "401" not in contract["paths"]["/api/v1/auth/csrf"]["get"]["responses"]
        password = contract["components"]["schemas"]["RegisterInput"]["properties"]["password"]
        assert password["minLength"] == 12 and password["maxLength"] == 128
        patch = contract["components"]["schemas"]["ProfilePatch"]
        assert patch["additionalProperties"] is False and patch["minProperties"] == 1
        assert patch["properties"]["display_name"]["type"] == "string"
        public = contract["components"]["schemas"]["UserPublic"]
        assert set(public["properties"]) == {"id", "username", "display_name", "created_at", "bio", "avatar_url"}
        assert any(item.get("format") == "uri" for item in public["properties"]["avatar_url"]["anyOf"])
        for name in ["CategoryInput", "CategoryPatch", "PostInput", "PostPatch"]:
            assert contract["components"]["schemas"][name]["additionalProperties"] is False
        assert client.get("/api/v1/admin/users/{user_id}/roles").status_code == 405


def test_startup_rejects_invalid_configuration_without_secret(monkeypatch, caplog):
    monkeypatch.setenv("DATABASE_URL", "sqlite://secret-marker")
    with pytest.raises(ConfigurationError) as error:
        with TestClient(app):
            pass
    assert "DATABASE_URL" in str(error.value)
    assert "secret-marker" not in str(error.value) + caplog.text

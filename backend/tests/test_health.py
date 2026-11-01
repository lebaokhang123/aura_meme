import pytest
from fastapi.testclient import TestClient

from app.config import ConfigurationError
from app.main import app


def test_health_and_openapi_without_a_database(monkeypatch):
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
        assert set(contract["paths"]) == {"/health"}
        assert contract["paths"]["/health"]["get"]["operationId"] == "health"
        model = contract["components"]["schemas"]["HealthResponse"]
        assert model["required"] == ["status"]
        assert model["properties"]["status"]["const"] == "ok"
        assert "not-a-real-secret" not in schema.text
        assert client.get("/api/v1/auth/login").status_code == 404


def test_startup_rejects_invalid_configuration_without_secret(monkeypatch, caplog):
    monkeypatch.setenv("DATABASE_URL", "sqlite://secret-marker")
    with pytest.raises(ConfigurationError) as error:
        with TestClient(app):
            pass
    assert "DATABASE_URL" in str(error.value)
    assert "secret-marker" not in str(error.value) + caplog.text

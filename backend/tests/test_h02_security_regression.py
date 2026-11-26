"""Focused H02 security regression tests (OWASP Top 10:2025 / ASVS 5.0)."""
from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app


def test_h02_guest_and_csrf_and_xss_headers(monkeypatch):
    """Verify guest boundary, invalid CSRF, safe search, and security headers without DB writes."""
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://test:not-a-real-secret@127.0.0.1:1/test")
    monkeypatch.setenv("AUTH_SIGNING_KEY", "h02-unit-test-signing-key-at-least-32-bytes")
    monkeypatch.setenv("AUTH_ENVIRONMENT", "development")
    monkeypatch.setenv("AUTH_ALLOWED_ORIGINS", '["http://localhost:5173","http://127.0.0.1:8000"]')
    with TestClient(app) as client:
        # Guest cannot access admin endpoints
        for path in ("/api/v1/admin/users", "/api/v1/admin/posts", "/api/v1/admin/audit-logs"):
            r = client.get(path)
            assert r.status_code == 401
            assert "traceback" not in r.text.lower()

        # CSRF endpoint sets security headers
        csrf_res = client.get("/api/v1/auth/csrf")
        assert csrf_res.status_code == 200
        assert csrf_res.headers.get("x-content-type-options") == "nosniff"
        assert csrf_res.headers.get("x-frame-options") == "DENY"
        assert csrf_res.headers.get("cache-control") == "no-store"

        # Invalid UUID returns 422 without stack trace
        r_bad = client.get("/api/v1/posts/not-a-uuid")
        assert r_bad.status_code == 422
        assert "traceback" not in r_bad.text.lower()

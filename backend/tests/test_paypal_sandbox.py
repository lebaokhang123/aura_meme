"""Unit and integration tests for PayPal Sandbox adapter and API endpoints."""
from datetime import datetime, timedelta, timezone
import json
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from pydantic import SecretStr

from app.paypal_adapter import (
    PaypalAdapter,
    PaypalApiError,
    PaypalConfigurationError,
)
from app.premium_plans import PLANS, get_plan


def test_paypal_adapter_initialization_and_configuration():
    # Unconfigured adapter
    unconfigured = PaypalAdapter()
    assert unconfigured.is_configured() is False
    assert unconfigured.get_client_id() is None
    with pytest.raises(PaypalConfigurationError):
        unconfigured.get_access_token()

    # Configured adapter
    adapter = PaypalAdapter(
        client_id="test_client_id_123",
        client_secret="test_client_secret_456",
        mode="sandbox",
        webhook_id="WH-123456",
    )
    assert adapter.is_configured() is True
    assert adapter.get_client_id() == "test_client_id_123"
    assert adapter.mode == "sandbox"
    assert adapter.base_url == "https://api-m.sandbox.paypal.com"


def test_paypal_adapter_create_order_payload():
    adapter = PaypalAdapter(
        client_id="test_client_id",
        client_secret="test_secret",
    )

    fake_res = {
        "id": "PAYPAL-ORDER-123",
        "status": "CREATED",
        "links": [
            {"rel": "self", "href": "https://api-m.sandbox.paypal.com/v2/checkout/orders/PAYPAL-ORDER-123"},
            {"rel": "approve", "href": "https://www.sandbox.paypal.com/checkoutnow?token=PAYPAL-ORDER-123"},
        ],
    }

    with patch.object(adapter, "get_access_token", return_value="mock_access_token"), \
         patch.object(adapter, "_http_request", return_value=fake_res) as mock_http:
        res = adapter.create_order("AM-PP-PLUS-TEST123", "plus")
        assert res["id"] == "PAYPAL-ORDER-123"
        assert res["approve_url"] == "https://www.sandbox.paypal.com/checkoutnow?token=PAYPAL-ORDER-123"
        assert res["status"] == "CREATED"

        # Check call arguments
        mock_http.assert_called_once()
        args, kwargs = mock_http.call_args
        method, path = args[0], args[1]
        assert method == "POST"
        assert path == "/v2/checkout/orders"
        sent_body = json.loads(kwargs["data"].decode("utf-8"))
        assert sent_body["intent"] == "CAPTURE"
        assert sent_body["purchase_units"][0]["amount"]["currency_code"] == "USD"
        assert sent_body["purchase_units"][0]["amount"]["value"] == "5.00"
        assert sent_body["purchase_units"][0]["reference_id"] == "AM-PP-PLUS-TEST123"


def test_paypal_adapter_verify_capture():
    adapter = PaypalAdapter(client_id="test", client_secret="test")

    valid_capture = {
        "status": "COMPLETED",
        "purchase_units": [
            {
                "reference_id": "AM-PP-PRIME-TEST999",
                "payments": {
                    "captures": [
                        {
                            "id": "CAP-123456",
                            "status": "COMPLETED",
                            "amount": {
                                "currency_code": "USD",
                                "value": "50.00",
                            },
                        }
                    ]
                },
            }
        ],
    }

    # Successful verification
    ok, msg = adapter.verify_capture(valid_capture, expected_amount_cents=5000, expected_order_code="AM-PP-PRIME-TEST999")
    assert ok is True
    assert "Capture verified successfully" in msg

    # Status not completed
    invalid_status = json.loads(json.dumps(valid_capture))
    invalid_status["status"] = "PENDING"
    ok, msg = adapter.verify_capture(invalid_status, expected_amount_cents=5000)
    assert ok is False
    assert "Capture status is not COMPLETED" in msg

    # Currency not USD
    invalid_curr = json.loads(json.dumps(valid_capture))
    invalid_curr["purchase_units"][0]["payments"]["captures"][0]["amount"]["currency_code"] = "EUR"
    ok, msg = adapter.verify_capture(invalid_curr, expected_amount_cents=5000)
    assert ok is False
    assert "Invalid currency" in msg

    # Amount mismatch
    invalid_amt = json.loads(json.dumps(valid_capture))
    invalid_amt["purchase_units"][0]["payments"]["captures"][0]["amount"]["value"] = "10.00"
    ok, msg = adapter.verify_capture(invalid_amt, expected_amount_cents=5000)
    assert ok is False
    assert "Amount mismatch" in msg

    # Order code mismatch
    ok, msg = adapter.verify_capture(valid_capture, expected_amount_cents=5000, expected_order_code="DIFFERENT-CODE")
    assert ok is False
    assert "Order reference mismatch" in msg


def test_paypal_status_and_schema_contract(monkeypatch):
    """Verify OpenAPI schema contract and public PayPal status exposure."""
    from fastapi.testclient import TestClient
    from app.main import app

    monkeypatch.setenv("AUTH_SIGNING_KEY", "test-only-signing-key-with-at-least-32-bytes")
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://test:not-a-real-secret@127.0.0.1:1/test")

    with TestClient(app, base_url="https://testserver") as client:
        # Check /openapi.json contract
        schema_res = client.get("/openapi.json")
        assert schema_res.status_code == 200
        schema = schema_res.json()
        paths = schema["paths"]

        assert "/api/v1/premium/orders/{order_code}/capture" in paths
        capture_op = paths["/api/v1/premium/orders/{order_code}/capture"]["post"]
        assert capture_op["operationId"] == "captureSubscriptionOrder"

        assert "/api/v1/premium/paypal/webhook" in paths
        webhook_op = paths["/api/v1/premium/paypal/webhook"]["post"]
        assert webhook_op["operationId"] == "handlePaypalWebhook"

        # Check status response includes PayPal fields
        status_res = client.get("/api/v1/premium/status")
        assert status_res.status_code == 200
        status_data = status_res.json()
        assert "paypal_configured" in status_data
        assert "paypal_client_id" in status_data
        assert "paypal_mode" in status_data
        assert status_data["paypal_mode"] == "sandbox"


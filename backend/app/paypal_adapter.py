"""PayPal Checkout Orders v2 Sandbox Adapter for AuraMeme."""
import base64
import json
import logging
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from typing import Any

from app.premium_plans import PlanDefinition, get_plan

logger = logging.getLogger("aurameme.paypal")


class PaypalError(Exception):
    """Base exception for PayPal operations."""
    pass


class PaypalConfigurationError(PaypalError):
    """Raised when PayPal credentials or settings are missing or invalid."""
    pass


class PaypalApiError(PaypalError):
    """Raised when an API request to PayPal fails."""
    def __init__(self, message: str, status_code: int = 502, response_body: Any = None):
        super().__init__(message)
        self.status_code = status_code
        self.response_body = response_body


class PaypalAdapter:
    """Official PayPal Checkout Adapter using Orders v2 Sandbox API."""

    SANDBOX_BASE_URL = "https://api-m.sandbox.paypal.com"
    LIVE_BASE_URL = "https://api-m.paypal.com"

    def __init__(
        self,
        client_id: str | None = None,
        client_secret: str | None = None,
        mode: str = "sandbox",
        webhook_id: str | None = None,
        return_url: str = "http://localhost:5173/premium/checkout",
        cancel_url: str = "http://localhost:5173/premium",
    ):
        self.client_id = client_id.strip() if client_id else None
        self.client_secret = client_secret.strip() if client_secret else None
        self.mode = mode.lower() if mode else "sandbox"
        self.webhook_id = webhook_id.strip() if webhook_id else None
        self.return_url = return_url
        self.cancel_url = cancel_url

        # Task 5 enforces sandbox mode; live is disabled
        self.base_url = self.SANDBOX_BASE_URL

        # In-memory cached token
        self._cached_token: str | None = None
        self._token_expires_at: float = 0.0

    def is_configured(self) -> bool:
        """Returns True only when both Client ID and Client Secret are present."""
        return bool(self.client_id and self.client_secret)

    def get_client_id(self) -> str | None:
        """Public Client ID safely exposed to frontend SDK; Client Secret is NEVER exposed."""
        return self.client_id

    def _http_request(
        self,
        method: str,
        path: str,
        headers: dict[str, str],
        data: bytes | None = None,
        timeout: int = 15,
    ) -> dict[str, Any]:
        """Performs a synchronous HTTP request to PayPal API with robust error handling."""
        url = f"{self.base_url}{path}"
        req = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                status = resp.status
                body = resp.read()
                if body:
                    try:
                        return json.loads(body.decode("utf-8"))
                    except json.JSONDecodeError:
                        return {"raw": body.decode("utf-8", errors="replace")}
                return {}
        except urllib.error.HTTPError as e:
            err_body = None
            try:
                raw = e.read()
                err_body = json.loads(raw.decode("utf-8"))
            except Exception:
                pass
            logger.error(
                "PayPal API error: %s %s -> HTTP %d: %s",
                method,
                path,
                e.code,
                err_body or e.reason,
            )
            raise PaypalApiError(
                f"PayPal API returned error {e.code}: {e.reason}",
                status_code=e.code,
                response_body=err_body,
            ) from e
        except urllib.error.URLError as e:
            logger.error("PayPal connection failed: %s %s: %s", method, path, e.reason)
            raise PaypalApiError(f"PayPal connection error: {e.reason}", status_code=504) from e

    def get_access_token(self, force_refresh: bool = False) -> str:
        """Fetches an OAuth2 bearer access token from PayPal using client credentials grant."""
        if not self.is_configured():
            raise PaypalConfigurationError("PayPal Sandbox credentials (CLIENT_ID / CLIENT_SECRET) are not configured.")

        now_ts = datetime.now(timezone.utc).timestamp()
        if not force_refresh and self._cached_token and now_ts < (self._token_expires_at - 60):
            return self._cached_token

        auth_str = f"{self.client_id}:{self.client_secret}"
        encoded_auth = base64.b64encode(auth_str.encode("utf-8")).decode("utf-8")

        headers = {
            "Authorization": f"Basic {encoded_auth}",
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json",
            "Accept-Language": "en_US",
        }
        body = b"grant_type=client_credentials"

        data = self._http_request("POST", "/v1/oauth2/token", headers=headers, data=body)
        token = data.get("access_token")
        expires_in = data.get("expires_in", 32400)
        if not token:
            raise PaypalApiError("Failed to obtain PayPal access token: empty response.")

        self._cached_token = token
        self._token_expires_at = now_ts + int(expires_in)
        return token

    def create_order(
        self,
        order_code: str,
        plan_tier: str,
        return_url: str | None = None,
        cancel_url: str | None = None,
    ) -> dict[str, Any]:
        """Creates an authoritative PayPal order with intent=CAPTURE for a given plan."""
        plan: PlanDefinition = get_plan(plan_tier)
        token = self.get_access_token()

        amount_str = f"{plan.amount_usd_cents / 100:.2f}"
        payload = {
            "intent": "CAPTURE",
            "purchase_units": [
                {
                    "reference_id": order_code,
                    "custom_id": order_code,
                    "description": f"AuraMeme {plan.name} Membership ({plan.duration_days} days)",
                    "amount": {
                        "currency_code": "USD",
                        "value": amount_str,
                    },
                }
            ],
            "application_context": {
                "brand_name": "AuraMeme",
                "landing_page": "NO_PREFERENCE",
                "user_action": "PAY_NOW",
                "return_url": return_url or self.return_url,
                "cancel_url": cancel_url or self.cancel_url,
            },
        }

        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "PayPal-Request-Id": order_code,
        }

        data_bytes = json.dumps(payload).encode("utf-8")
        res = self._http_request("POST", "/v2/checkout/orders", headers=headers, data=data_bytes)

        paypal_order_id = res.get("id")
        approve_url = None
        for link in res.get("links", []):
            if link.get("rel") == "approve":
                approve_url = link.get("href")
                break

        return {
            "id": paypal_order_id,
            "status": res.get("status", "CREATED"),
            "approve_url": approve_url,
            "raw": res,
        }

    def capture_order(self, paypal_order_id: str, idempotency_key: str | None = None) -> dict[str, Any]:
        """Captures payment for an approved PayPal order. Authoritative step before activation."""
        token = self.get_access_token()
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        if idempotency_key:
            headers["PayPal-Request-Id"] = f"capture_{idempotency_key}"

        path = f"/v2/checkout/orders/{urllib.parse.quote(paypal_order_id)}/capture"
        res = self._http_request("POST", path, headers=headers, data=b"{}")
        return res

    def get_order_details(self, paypal_order_id: str) -> dict[str, Any]:
        """Fetches live order details directly from PayPal Orders v2."""
        token = self.get_access_token()
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        path = f"/v2/checkout/orders/{urllib.parse.quote(paypal_order_id)}"
        return self._http_request("GET", path, headers=headers)

    def verify_capture(
        self,
        capture_data: dict[str, Any],
        expected_amount_cents: int,
        expected_order_code: str | None = None,
    ) -> tuple[bool, str]:
        """Strict verification of a capture payload against expected amount, currency (USD), and status."""
        status = capture_data.get("status")
        if status != "COMPLETED":
            return False, f"Capture status is not COMPLETED (got '{status}')."

        purchase_units = capture_data.get("purchase_units") or []
        if not purchase_units:
            return False, "Capture data contains no purchase units."

        unit = purchase_units[0]
        if expected_order_code:
            ref_id = unit.get("reference_id") or unit.get("custom_id")
            if ref_id and ref_id != expected_order_code:
                return False, f"Order reference mismatch (expected '{expected_order_code}', got '{ref_id}')."

        payments = unit.get("payments", {})
        captures = payments.get("captures", [])
        if not captures:
            return False, "No capture transaction records found in purchase unit."

        capture_obj = captures[0]
        cap_status = capture_obj.get("status")
        if cap_status != "COMPLETED":
            return False, f"Inner capture status is not COMPLETED (got '{cap_status}')."

        amount_info = capture_obj.get("amount", {})
        currency = amount_info.get("currency_code")
        if currency != "USD":
            return False, f"Invalid currency: expected 'USD', got '{currency}'."

        try:
            val_float = float(amount_info.get("value", "0"))
            val_cents = round(val_float * 100)
        except (ValueError, TypeError):
            return False, "Invalid amount value format in capture response."

        if val_cents != expected_amount_cents:
            return False, f"Amount mismatch: expected {expected_amount_cents} cents, got {val_cents} cents."

        return True, "Capture verified successfully."

    def verify_webhook_signature(
        self,
        headers: dict[str, str],
        raw_body: bytes,
    ) -> bool:
        """Verifies webhook signature using PayPal verify-webhook-signature API."""
        if not self.is_configured() or not self.webhook_id:
            logger.warning("PayPal webhook verification skipped: webhook_id or credentials not configured.")
            return False

        token = self.get_access_token()
        try:
            body_json = json.loads(raw_body.decode("utf-8"))
        except Exception:
            return False

        payload = {
            "auth_algo": headers.get("paypal-auth-algo") or headers.get("PAYPAL-AUTH-ALGO"),
            "cert_url": headers.get("paypal-cert-url") or headers.get("PAYPAL-CERT-URL"),
            "transmission_id": headers.get("paypal-transmission-id") or headers.get("PAYPAL-TRANSMISSION-ID"),
            "transmission_sig": headers.get("paypal-transmission-sig") or headers.get("PAYPAL-TRANSMISSION-SIG"),
            "transmission_time": headers.get("paypal-transmission-time") or headers.get("PAYPAL-TRANSMISSION-TIME"),
            "webhook_id": self.webhook_id,
            "webhook_event": body_json,
        }

        # Validate presence of all transmission headers
        if not all(payload.values()):
            return False

        req_headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        try:
            data = self._http_request(
                "POST",
                "/v1/notifications/verify-webhook-signature",
                headers=req_headers,
                data=json.dumps(payload).encode("utf-8"),
            )
            return data.get("verification_status") == "SUCCESS"
        except Exception as e:
            logger.error("Failed to verify webhook signature with PayPal: %s", e)
            return False

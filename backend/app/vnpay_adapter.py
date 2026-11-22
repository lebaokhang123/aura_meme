"""VNPAY Sandbox payment adapter and HMAC-SHA512 cryptographic verification."""
from datetime import datetime
import hashlib
import hmac
from typing import Any
import urllib.parse
from zoneinfo import ZoneInfo

VN_TZ = ZoneInfo("Asia/Ho_Chi_Minh")


class VnpayConfigurationError(ValueError):
    """Raised when VNPAY sandbox credentials or VND pricing approval are missing."""


class VnpayAdapter:
    def __init__(
        self,
        tmn_code: str | None,
        hash_secret: str | None,
        payment_url: str = "https://sandbox.vnpayment.vn/paymentv2/vpcpay.html",
        return_url: str = "http://127.0.0.1:5173/premium",
        pricing_approved: bool = False,
    ):
        self.tmn_code = tmn_code
        self.hash_secret = hash_secret
        self.payment_url = payment_url
        self.return_url = return_url
        self.pricing_approved = pricing_approved

    def is_configured(self) -> bool:
        return bool(self.tmn_code and self.hash_secret and self.pricing_approved)

    def create_payment_url(
        self,
        order_code: str,
        amount_vnd: int,
        order_info: str,
        ip_addr: str = "127.0.0.1",
        locale: str = "vn",
        created_at: datetime | None = None,
    ) -> str:
        if not self.tmn_code or not self.hash_secret:
            raise VnpayConfigurationError("VNPAY sandbox merchant credentials are not configured.")
        if not self.pricing_approved:
            raise VnpayConfigurationError("VNPAY VND pricing has not been approved by Owner.")
        if amount_vnd <= 0:
            raise ValueError("Payment amount must be greater than zero.")

        now_vn = (created_at or datetime.now(VN_TZ)).astimezone(VN_TZ)
        create_date = now_vn.strftime("%Y%m%d%H%M%S")

        # VNPAY amount is in VND x 100
        vnp_amount = str(amount_vnd * 100)

        params: dict[str, str] = {
            "vnp_Version": "2.1.0",
            "vnp_Command": "pay",
            "vnp_TmnCode": self.tmn_code,
            "vnp_Amount": vnp_amount,
            "vnp_CurrCode": "VND",
            "vnp_TxnRef": order_code,
            "vnp_OrderInfo": order_info,
            "vnp_OrderType": "other",
            "vnp_Locale": "vn" if locale == "vi" else "en",
            "vnp_ReturnUrl": self.return_url,
            "vnp_IpAddr": ip_addr or "127.0.0.1",
            "vnp_CreateDate": create_date,
        }

        # Alphabetically sort and build query string for hashing
        sorted_keys = sorted(params.keys())
        query_parts: list[str] = []
        for key in sorted_keys:
            val = params[key]
            if val is not None and str(val) != "":
                query_parts.append(f"{urllib.parse.quote_plus(key)}={urllib.parse.quote_plus(str(val))}")

        raw_query = "&".join(query_parts)
        secure_hash = self.calculate_signature(raw_query)

        return f"{self.payment_url}?{raw_query}&vnp_SecureHash={secure_hash}"

    def calculate_signature(self, data: str) -> str:
        if not self.hash_secret:
            raise VnpayConfigurationError("VNPAY hash secret is not set.")
        key_bytes = self.hash_secret.encode("utf-8")
        data_bytes = data.encode("utf-8")
        return hmac.new(key_bytes, data_bytes, hashlib.sha512).hexdigest()

    def verify_response(self, query_params: dict[str, Any]) -> tuple[bool, dict[str, Any]]:
        """Verify VNPAY checksum response or IPN callback."""
        received_hash = query_params.get("vnp_SecureHash") or query_params.get("vnp_securehash")
        if not received_hash or not self.hash_secret:
            return False, {}

        # Filter out vnp_SecureHash and vnp_SecureHashType
        filtered_params: dict[str, str] = {}
        for key, value in query_params.items():
            if key in {"vnp_SecureHash", "vnp_securehash", "vnp_SecureHashType", "vnp_securehashtype"}:
                continue
            if key.startswith("vnp_"):
                filtered_params[key] = str(value)

        sorted_keys = sorted(filtered_params.keys())
        query_parts: list[str] = []
        for key in sorted_keys:
            val = filtered_params[key]
            if val is not None and val != "":
                query_parts.append(f"{urllib.parse.quote_plus(key)}={urllib.parse.quote_plus(str(val))}")

        raw_query = "&".join(query_parts)
        expected_hash = self.calculate_signature(raw_query)

        is_valid = hmac.compare_digest(str(received_hash).lower(), expected_hash.lower())
        return is_valid, filtered_params

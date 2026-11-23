"""Google Identity Services / OpenID Connect backend verification and safe linking.

Security guarantees:
- Verifies Google ID token on backend (signature/issuer/audience/expiry/email_verified/sub).
- Uses immutable Google `sub` as provider identity, NEVER email-only matching for login.
- Blocks automatic email-collision takeover (returns 409 ACCOUNT_LINK_REQUIRED if local email exists).
- Account linking requires an active authenticated session + CSRF + current password verification.
- Never grants ADMIN role automatically.
- Handles duplicate concurrent callback safely without creating duplicate accounts.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
import base64
import hashlib
import hmac
import json
import re
import secrets
from typing import Literal
from uuid import uuid4

from fastapi import APIRouter, Depends, Request, Response
import httpx
from pydantic import BaseModel, ConfigDict, Field, SecretStr
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import IntegrityError

from app.auth import CSRF_HEADER, ERRORS, delete_cookie, guest_guard, set_cookie, user_private
from app.auth_schemas import UserPrivate
from app.config import GoogleAuthSettings

from app.models import AuthSession, Profile, Role, User, UserOAuthIdentity, UserRole
from app.password_reset import GOOGLE_ONLY_PASSWORD_PREFIX
from app.permissions import require_account_csrf
from app.security import IDLE_SECONDS, AuthError, digest

router = APIRouter(prefix="/api/v1/auth/google", tags=["Auth"])

GOOGLE_TOKENINFO_URL = "https://oauth2.googleapis.com/tokeninfo"
VALID_ISSUERS = frozenset({"accounts.google.com", "https://accounts.google.com"})


@dataclass(frozen=True)
class VerifiedGoogleClaims:
    sub: str
    email: str
    email_verified: bool
    name: str
    nonce: str | None = None


class GoogleConfigResponse(BaseModel):
    enabled: bool
    client_id: str | None = None


class GoogleLoginInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id_token: SecretStr = Field(min_length=20, max_length=8192)
    nonce: str | None = Field(default=None, max_length=128)
    username: str | None = Field(default=None, min_length=3, max_length=32, pattern=r"^[a-z0-9_]+$")


class GoogleOnboardingRequiredResponse(BaseModel):
    status: Literal["needs_onboarding"] = "needs_onboarding"
    onboarding_token: str
    email: str
    display_name: str
    suggested_tag: str


class GoogleOnboardingInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    onboarding_token: str = Field(min_length=20, max_length=2048)
    username: str = Field(min_length=3, max_length=32, pattern=r"^[a-z0-9_]+$")



class GoogleLinkInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id_token: SecretStr = Field(min_length=20, max_length=8192)
    current_password: SecretStr = Field(min_length=1, max_length=128)


class GoogleLinkResponse(BaseModel):
    linked: bool = True
    provider: str = "google"


class GoogleTokenVerifier:
    def __init__(self, settings: GoogleAuthSettings):
        self.settings = settings

    @property
    def configured(self) -> bool:
        return bool((self.settings.google_client_id or "").strip())

    def verify_id_token(self, raw_token: str, now_ts: int, expected_nonce: str | None = None) -> VerifiedGoogleClaims:
        client_id = (self.settings.google_client_id or "").strip()
        if not client_id:
            raise AuthError(503, "GOOGLE_AUTH_NOT_CONFIGURED", "Google login is not configured on this server.")

        try:
            with httpx.Client(timeout=5.0) as client:
                resp = client.get(GOOGLE_TOKENINFO_URL, params={"id_token": raw_token})
        except httpx.HTTPError:
            raise AuthError(502, "GOOGLE_VERIFY_UNAVAILABLE", "Unable to verify Google credentials right now.") from None

        if resp.status_code != 200:
            raise AuthError(401, "GOOGLE_TOKEN_INVALID", "Invalid Google authentication token.")

        try:
            claims = resp.json()
        except ValueError:
            raise AuthError(401, "GOOGLE_TOKEN_INVALID", "Invalid Google authentication token.") from None

        return self.validate_claims(claims, client_id=client_id, now_ts=now_ts, expected_nonce=expected_nonce)

    @staticmethod
    def validate_claims(
        claims: dict,
        *,
        client_id: str,
        now_ts: int,
        expected_nonce: str | None = None,
    ) -> VerifiedGoogleClaims:
        if not isinstance(claims, dict):
            raise AuthError(401, "GOOGLE_TOKEN_INVALID", "Invalid Google authentication token.")

        aud = claims.get("aud")
        iss = claims.get("iss")
        sub = claims.get("sub")
        email = claims.get("email")
        email_verified_raw = claims.get("email_verified")
        exp_raw = claims.get("exp")

        if aud != client_id:
            raise AuthError(401, "GOOGLE_TOKEN_INVALID", "Google token audience mismatch.")
        if iss not in VALID_ISSUERS:
            raise AuthError(401, "GOOGLE_TOKEN_INVALID", "Google token issuer mismatch.")
        try:
            exp = int(exp_raw)
        except (TypeError, ValueError):
            raise AuthError(401, "GOOGLE_TOKEN_INVALID", "Google token expiry invalid.") from None
        if exp <= now_ts:
            raise AuthError(401, "GOOGLE_TOKEN_EXPIRED", "Google authentication token has expired.")

        if not isinstance(sub, str) or not sub.strip() or len(sub) > 255:
            raise AuthError(401, "GOOGLE_TOKEN_INVALID", "Google subject missing.")
        if not isinstance(email, str) or "@" not in email:
            raise AuthError(401, "GOOGLE_TOKEN_INVALID", "Google email missing.")

        email_verified = email_verified_raw is True or str(email_verified_raw).lower() == "true"
        if not email_verified:
            raise AuthError(403, "GOOGLE_EMAIL_UNVERIFIED", "Google account email must be verified.")

        token_nonce = claims.get("nonce")
        if expected_nonce is not None and token_nonce != expected_nonce:
            raise AuthError(401, "GOOGLE_NONCE_MISMATCH", "Google authentication nonce mismatch.")

        display_name = (claims.get("name") or email.split("@", 1)[0] or "Aura User").strip()[:25] or "Aura User"
        return VerifiedGoogleClaims(
            sub=sub.strip(),
            email=email.strip().lower(),
            email_verified=True,
            name=display_name,
            nonce=token_nonce if isinstance(token_nonce, str) else None,
        )


def suggest_tag(email: str) -> str:
    prefix = re.sub(r"[^a-z0-9_]", "_", email.split("@", 1)[0].lower())
    prefix = re.sub(r"_+", "_", prefix).strip("_")
    if len(prefix) < 3:
        prefix = "aura_user"
    return prefix[:20]


def create_onboarding_token(runtime, sub: str, email: str, name: str, expires_seconds: int = 900) -> str:
    now = runtime.now()
    exp = int(now.timestamp()) + expires_seconds
    payload_obj = {"sub": sub, "email": email, "name": name, "exp": exp}
    payload_bytes = json.dumps(payload_obj, separators=(",", ":"), sort_keys=True).encode("utf-8")
    payload_b64 = base64.urlsafe_b64encode(payload_bytes).decode("ascii").rstrip("=")
    sig = hmac.new(runtime.key, f"google_onboarding:{payload_b64}".encode("utf-8"), hashlib.sha256).hexdigest()
    return f"{payload_b64}.{sig}"


def verify_onboarding_token(runtime, token: str) -> dict:
    parts = token.split(".")
    if len(parts) != 2:
        raise AuthError(400, "INVALID_ONBOARDING_TOKEN", "Phiên đăng ký Google không hợp lệ.")
    payload_b64, sig = parts
    expected_sig = hmac.new(runtime.key, f"google_onboarding:{payload_b64}".encode("utf-8"), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(sig, expected_sig):
        raise AuthError(400, "INVALID_ONBOARDING_TOKEN", "Phiên đăng ký Google không hợp lệ hoặc đã bị thay đổi.")
    try:
        padded = payload_b64 + "=" * (-len(payload_b64) % 4)
        payload_bytes = base64.urlsafe_b64decode(padded.encode("ascii"))
        data = json.loads(payload_bytes.decode("utf-8"))
    except Exception:
        raise AuthError(400, "INVALID_ONBOARDING_TOKEN", "Dữ liệu đăng ký Google không hợp lệ.") from None
    now_ts = int(runtime.now().timestamp())
    if data.get("exp", 0) < now_ts:
        raise AuthError(400, "ONBOARDING_TOKEN_EXPIRED", "Phiên đăng ký Google đã hết hạn. Vui lòng đăng nhập lại.")
    return data


def _generate_username(db, email: str) -> str:
    prefix = re.sub(r"[^a-z0-9_]", "_", email.split("@", 1)[0].lower())
    prefix = re.sub(r"_+", "_", prefix).strip("_")
    if len(prefix) < 3:
        prefix = "aura_user"
    base = prefix[:20]
    candidate = base
    for _ in range(10):
        if db.scalar(select(User.id).where(User.username == candidate)) is None:
            return candidate
        candidate = f"{base[:16]}_{secrets.token_hex(3)}"
    return f"u_{secrets.token_hex(6)}"


@router.get("/config", response_model=GoogleConfigResponse, operation_id="getGoogleAuthConfig")
def get_google_config(request: Request):
    verifier: GoogleTokenVerifier = request.app.state.google_auth
    return GoogleConfigResponse(
        enabled=verifier.configured,
        client_id=(verifier.settings.google_client_id or "").strip() or None,
    )


@router.post(
    "/login",
    response_model=UserPrivate | GoogleOnboardingRequiredResponse,
    operation_id="googleLogin",
    responses={status: ERRORS[status] for status in (401, 403, 409, 422, 429, 500)} | {503: ERRORS[500]},
    openapi_extra=CSRF_HEADER,
)
def google_login(payload: GoogleLoginInput, request: Request, response: Response, pre=Depends(guest_guard)):
    runtime = request.app.state.auth
    client_ip = request.client.host if request.client else "unknown"
    runtime.limiter.check(f"google:login:{client_ip}", 15, 600)

    verifier: GoogleTokenVerifier = request.app.state.google_auth
    now = runtime.now()
    claims = verifier.verify_id_token(
        payload.id_token.get_secret_value(),
        now_ts=int(now.timestamp()),
        expected_nonce=payload.nonce,
    )

    with request.app.state.auth_session_factory() as db, db.begin():
        identity = db.scalar(
            select(UserOAuthIdentity)
            .where(UserOAuthIdentity.provider == "google", UserOAuthIdentity.provider_sub == claims.sub)
            .with_for_update()
        )
        if identity is not None:
            user = db.scalar(select(User).where(User.id == identity.user_id).with_for_update())
            if user is None or user.status != "active":
                raise AuthError(403, "ACCOUNT_INACTIVE", "Tài khoản không còn hoạt động.")
            identity.email = claims.email
            identity.email_verified = claims.email_verified
            identity.updated_at = now
        else:
            # Anti-takeover rule: NEVER auto-merge into an existing local account solely by email match!
            existing_email_user = db.scalar(select(User).where(User.email == claims.email))
            if existing_email_user is not None:
                raise AuthError(
                    409,
                    "ACCOUNT_LINK_REQUIRED",
                    "Email này đã thuộc về một tài khoản hiện có. Vui lòng đăng nhập bằng mật khẩu trước rồi liên kết Google.",
                )

            # If brand new user and no username provided -> return onboarding token
            if payload.username is None:
                return GoogleOnboardingRequiredResponse(
                    status="needs_onboarding",
                    onboarding_token=create_onboarding_token(runtime, claims.sub, claims.email, claims.name),
                    email=claims.email,
                    display_name=claims.name,
                    suggested_tag=suggest_tag(claims.email),
                )

            # If username is provided, validate uniqueness
            if db.scalar(select(User.id).where(User.username == payload.username)) is not None:
                raise AuthError(409, "USERNAME_EXISTS", "Tag đã được sử dụng, vui lòng chọn tag khác.")

            from app.aura_lock import lock_aura_mutation
            from app.aura_runtime import initialize_progress

            lock_aura_mutation(db)
            user_id = uuid4()
            sentinel_hash = GOOGLE_ONLY_PASSWORD_PREFIX + secrets.token_hex(24)
            user = User(
                id=user_id,
                username=payload.username,
                email=claims.email,
                password_hash=sentinel_hash,
                status="active",
                created_at=now,
                updated_at=now,
            )
            db.add(user)
            db.add(Profile(user_id=user_id, display_name=claims.name, updated_at=now))
            db.execute(
                insert(Role)
                .values(id=uuid4(), code="USER", description="Standard AuraMeme user")
                .on_conflict_do_nothing(index_elements=["code"])
            )
            role_id = db.scalar(select(Role.id).where(Role.code == "USER"))
            db.add(UserRole(user_id=user_id, role_id=role_id, granted_at=now))
            db.add(
                UserOAuthIdentity(
                    id=uuid4(),
                    user_id=user_id,
                    provider="google",
                    provider_sub=claims.sub,
                    email=claims.email,
                    email_verified=claims.email_verified,
                    created_at=now,
                    updated_at=now,
                )
            )
            try:
                db.flush()
            except IntegrityError:
                raise AuthError(409, "CONFLICT", "Tài khoản Google này đang được xử lý. Vui lòng thử lại.") from None
            initialize_progress(db, user_id, now)

        raw_session = secrets.token_urlsafe(32)
        db.add(
            AuthSession(
                id=uuid4(),
                user_id=user.id,
                token_hash=digest(raw_session),
                created_at=now,
                expires_at=now + timedelta(seconds=IDLE_SECONDS),
                revoked_at=None,
            )
        )
        db.flush()
        user_dto = user_private(db, user)
        runtime.consume_pre(pre)

    set_cookie(response, runtime, "am_session", raw_session, IDLE_SECONDS)
    delete_cookie(response, runtime, runtime.pre_cookie)
    return user_dto


@router.post(
    "/onboarding",
    response_model=UserPrivate,
    operation_id="googleOnboarding",
    responses={status: ERRORS[status] for status in (400, 401, 403, 409, 422, 429, 500)},
    openapi_extra=CSRF_HEADER,
)
def google_onboarding(payload: GoogleOnboardingInput, request: Request, response: Response, pre=Depends(guest_guard)):
    runtime = request.app.state.auth
    client_ip = request.client.host if request.client else "unknown"
    runtime.limiter.check(f"google:onboarding:{client_ip}", 15, 600)

    data = verify_onboarding_token(runtime, payload.onboarding_token)
    sub = data["sub"]
    email = data["email"]
    name = (data.get("name") or "Aura User").strip()[:25] or "Aura User"
    username = payload.username.strip().lower()

    now = runtime.now()
    raw_session = secrets.token_urlsafe(32)

    with request.app.state.auth_session_factory() as db, db.begin():
        existing_identity = db.scalar(
            select(UserOAuthIdentity).where(UserOAuthIdentity.provider == "google", UserOAuthIdentity.provider_sub == sub)
        )
        if existing_identity is not None:
            user = db.scalar(select(User).where(User.id == existing_identity.user_id).with_for_update())
            if user is None or user.status != "active":
                raise AuthError(403, "ACCOUNT_INACTIVE", "Tài khoản không còn hoạt động.")
        else:
            if db.scalar(select(User.id).where(User.email == email)) is not None:
                raise AuthError(409, "ACCOUNT_LINK_REQUIRED", "Email này đã thuộc về một tài khoản hiện có.")
            if db.scalar(select(User.id).where(User.username == username)) is not None:
                raise AuthError(409, "USERNAME_EXISTS", "Tag đã được sử dụng, vui lòng chọn tag khác.")

            from app.aura_lock import lock_aura_mutation
            from app.aura_runtime import initialize_progress

            lock_aura_mutation(db)
            user_id = uuid4()
            sentinel_hash = GOOGLE_ONLY_PASSWORD_PREFIX + secrets.token_hex(24)
            user = User(
                id=user_id,
                username=username,
                email=email,
                password_hash=sentinel_hash,
                status="active",
                created_at=now,
                updated_at=now,
            )
            db.add(user)
            db.add(Profile(user_id=user_id, display_name=name, updated_at=now))
            db.execute(
                insert(Role)
                .values(id=uuid4(), code="USER", description="Standard AuraMeme user")
                .on_conflict_do_nothing(index_elements=["code"])
            )
            role_id = db.scalar(select(Role.id).where(Role.code == "USER"))
            db.add(UserRole(user_id=user_id, role_id=role_id, granted_at=now))
            db.add(
                UserOAuthIdentity(
                    id=uuid4(),
                    user_id=user_id,
                    provider="google",
                    provider_sub=sub,
                    email=email,
                    email_verified=True,
                    created_at=now,
                    updated_at=now,
                )
            )
            try:
                db.flush()
            except IntegrityError:
                raise AuthError(409, "CONFLICT", "Tài khoản Google hoặc tag này đang được xử lý. Vui lòng thử lại.") from None
            initialize_progress(db, user_id, now)

        db.add(
            AuthSession(
                id=uuid4(),
                user_id=user.id,
                token_hash=digest(raw_session),
                created_at=now,
                expires_at=now + timedelta(seconds=IDLE_SECONDS),
                revoked_at=None,
            )
        )
        db.flush()
        user_dto = user_private(db, user)
        runtime.consume_pre(pre)

    set_cookie(response, runtime, "am_session", raw_session, IDLE_SECONDS)
    delete_cookie(response, runtime, runtime.pre_cookie)
    return user_dto



@router.post(
    "/link",
    response_model=GoogleLinkResponse,
    operation_id="googleLinkAccount",
    responses={status: ERRORS[status] for status in (401, 403, 409, 422, 429, 500)} | {503: ERRORS[500]},
    openapi_extra=CSRF_HEADER,
)
def google_link_account(payload: GoogleLinkInput, request: Request, account=Depends(require_account_csrf)):
    runtime = request.app.state.auth
    runtime.limiter.check(f"google:link:{account.user.id}", 5, 600)

    # Verify account ownership with current local password before linking Google
    if (
        not account.user.password_hash
        or account.user.password_hash.startswith(GOOGLE_ONLY_PASSWORD_PREFIX)
        or not runtime.verify_password(account.user.password_hash, payload.current_password.get_secret_value())
    ):
        raise AuthError(403, "FORBIDDEN", "Mật khẩu hiện tại không chính xác.")

    verifier: GoogleTokenVerifier = request.app.state.google_auth
    now = runtime.now()
    claims = verifier.verify_id_token(payload.id_token.get_secret_value(), now_ts=int(now.timestamp()))

    existing = account.db.scalar(
        select(UserOAuthIdentity).where(
            UserOAuthIdentity.provider == "google",
            UserOAuthIdentity.provider_sub == claims.sub,
        )
    )
    if existing is not None:
        if existing.user_id == account.user.id:
            return GoogleLinkResponse(linked=True, provider="google")
        raise AuthError(409, "CONFLICT", "Tài khoản Google này đã được liên kết với một tài khoản khác.")

    account.db.add(
        UserOAuthIdentity(
            id=uuid4(),
            user_id=account.user.id,
            provider="google",
            provider_sub=claims.sub,
            email=claims.email,
            email_verified=claims.email_verified,
            created_at=now,
            updated_at=now,
        )
    )
    account.db.flush()
    return GoogleLinkResponse(linked=True, provider="google")

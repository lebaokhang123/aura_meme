"""Secure password recovery: neutral forgot-password + one-time hashed reset tokens."""
from __future__ import annotations

from datetime import timedelta
import secrets
from urllib.parse import urlencode
from uuid import uuid4

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, ConfigDict, EmailStr, Field, SecretStr, field_validator
from sqlalchemy import select, update

from app.auth import CSRF_HEADER, ERRORS, guest_guard
from app.auth_schemas import LoginInput, RegisterInput
from app.models import AuthSession, PasswordResetToken, Profile, User
from app.security import AuthError, digest

router = APIRouter(prefix="/api/v1/auth", tags=["Auth"])

RESET_TOKEN_TTL_MINUTES = 30
GOOGLE_ONLY_PASSWORD_PREFIX = "!google:"
NEUTRAL_FORGOT_MESSAGE = (
    "Nếu địa chỉ email tồn tại và đủ điều kiện khôi phục, chúng tôi đã gửi liên kết đặt lại mật khẩu."
)


class ForgotPasswordInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: EmailStr

    @field_validator("email", mode="before")
    @classmethod
    def normalize_email(cls, value):
        return value.strip().lower() if isinstance(value, str) else value


class ForgotPasswordResponse(BaseModel):
    ok: bool = True
    message: str


class ResetPasswordInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    token: SecretStr = Field(min_length=20, max_length=256)
    new_password: SecretStr = Field(json_schema_extra={"minLength": 12, "maxLength": 128})

    @field_validator("new_password")
    @classmethod
    def valid_password_encoding(cls, value):
        return LoginInput.valid_password_encoding(value)

    @field_validator("new_password")
    @classmethod
    def valid_password_length(cls, value):
        return RegisterInput.password_length(value)


class ResetPasswordResponse(BaseModel):
    ok: bool = True
    message: str


def is_google_only_account(password_hash: str | None) -> bool:
    return isinstance(password_hash, str) and password_hash.startswith(GOOGLE_ONLY_PASSWORD_PREFIX)


@router.post(
    "/forgot-password",
    response_model=ForgotPasswordResponse,
    operation_id="forgotPassword",
    responses={status: ERRORS[status] for status in (403, 422, 429, 500)},
    openapi_extra=CSRF_HEADER,
)
def forgot_password(payload: ForgotPasswordInput, request: Request, pre=Depends(guest_guard)):
    runtime = request.app.state.auth
    client_ip = request.client.host if request.client else "unknown"
    runtime.limiter.check(f"forgot:ip:{client_ip}", 10, 900)
    runtime.limiter.check(f"forgot:email:{digest(payload.email)}", 3, 900)

    now = runtime.now()
    email_to_send: tuple[str, str, str, str] | None = None

    with request.app.state.auth_session_factory() as db, db.begin():
        user = db.scalar(select(User).where(User.email == payload.email).with_for_update())
        if user is not None and user.status == "active" and not is_google_only_account(user.password_hash):
            # Invalidate prior unused reset tokens for this account
            db.execute(
                update(PasswordResetToken)
                .where(PasswordResetToken.user_id == user.id, PasswordResetToken.used_at.is_(None))
                .values(used_at=now)
            )
            raw_token = secrets.token_urlsafe(32)
            token_id = uuid4()
            db.add(
                PasswordResetToken(
                    id=token_id,
                    user_id=user.id,
                    token_hash=digest(raw_token),
                    expires_at=now + timedelta(minutes=RESET_TOKEN_TTL_MINUTES),
                    used_at=None,
                    created_at=now,
                )
            )
            db.flush()
            profile = db.get(Profile, user.id)
            display_name = profile.display_name if profile else user.username
            email_to_send = (user.email, display_name, raw_token, str(token_id))

    # Send outside DB transaction; never leak whether email exists or whether send failed.
    if email_to_send is not None:
        to_email, display_name, raw_token, token_id = email_to_send
        email_service = getattr(request.app.state, "email_service", None)
        if email_service is not None:
            base = email_service.settings.app_public_url.rstrip("/")
            reset_url = f"{base}/reset-password?{urlencode({'token': raw_token})}"
            email_service.send_password_reset_email(
                to_email=to_email,
                display_name=display_name,
                reset_url=reset_url,
                expires_minutes=RESET_TOKEN_TTL_MINUTES,
                dedupe_key=f"pwdreset:{token_id}",
            )

    return ForgotPasswordResponse(ok=True, message=NEUTRAL_FORGOT_MESSAGE)


@router.post(
    "/reset-password",
    response_model=ResetPasswordResponse,
    operation_id="resetPassword",
    responses={status: ERRORS[status] for status in (403, 422, 429, 500)} | {400: ERRORS[422]},
    openapi_extra=CSRF_HEADER,
)
def reset_password(payload: ResetPasswordInput, request: Request, pre=Depends(guest_guard)):
    runtime = request.app.state.auth
    client_ip = request.client.host if request.client else "unknown"
    runtime.limiter.check(f"reset:ip:{client_ip}", 10, 900)

    raw_token = payload.token.get_secret_value().strip()
    if not raw_token:
        raise AuthError(400, "INVALID_RESET_TOKEN", "Liên kết đặt lại mật khẩu không hợp lệ hoặc đã hết hạn.")

    token_hash = digest(raw_token)
    now = runtime.now()
    new_hash = runtime.hasher.hash(payload.new_password.get_secret_value())

    with request.app.state.auth_session_factory() as db, db.begin():
        record = db.scalar(
            select(PasswordResetToken)
            .where(PasswordResetToken.token_hash == token_hash)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        if record is None or record.used_at is not None or record.expires_at <= now:
            raise AuthError(400, "INVALID_RESET_TOKEN", "Liên kết đặt lại mật khẩu không hợp lệ hoặc đã hết hạn.")

        user = db.scalar(
            select(User)
            .where(User.id == record.user_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        if user is None or user.status != "active":
            raise AuthError(400, "INVALID_RESET_TOKEN", "Liên kết đặt lại mật khẩu không hợp lệ hoặc đã hết hạn.")

        if is_google_only_account(user.password_hash):
            record.used_at = now
            raise AuthError(
                400,
                "GOOGLE_ONLY_ACCOUNT",
                "Tài khoản này đăng nhập bằng Google và không sử dụng mật khẩu cục bộ.",
            )

        user.password_hash = new_hash
        user.updated_at = now
        record.used_at = now

        # Revoke all existing sessions cleanly; user must sign in again with the new password (no auto-login).
        db.execute(
            update(AuthSession)
            .where(AuthSession.user_id == user.id, AuthSession.revoked_at.is_(None))
            .values(revoked_at=now)
        )
        db.flush()

    return ResetPasswordResponse(
        ok=True,
        message="Đặt lại mật khẩu thành công. Vui lòng đăng nhập bằng mật khẩu mới.",
    )

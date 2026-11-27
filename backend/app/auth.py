"""P0 authentication: one PostgreSQL transaction per operation, no schema changes."""
from datetime import datetime, timedelta
import secrets
from urllib.parse import urlsplit
from uuid import uuid4

from fastapi import APIRouter, Depends, Request, Response
from fastapi.security import APIKeyCookie
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import IntegrityError

from app.auth_schemas import (
    CsrfResponse,
    ErrorResponse,
    LoginInput,
    RegisterInput,
    RegisterResponse,
    ResendVerificationInput,
    ResendVerificationResponse,
    UserPrivate,
    VerifyEmailInput,
    VerifyEmailResponse,
)
from app.models import AccountVerification, AuthSession, Profile, Role, User, UserRole

from app.security import ABSOLUTE_SECONDS, IDLE_SECONDS, PRE_TTL, TOKEN, AuthError, digest


router = APIRouter(prefix="/api/v1/auth", tags=["Auth"])
session_cookie = APIKeyCookie(name="am_session", auto_error=False, scheme_name="sessionCookie")
ERRORS = {status: {"model": ErrorResponse} for status in (400, 401, 403, 409, 422, 429, 500)}
CSRF_HEADER = {"parameters": [{"name": "X-CSRF-Token", "in": "header", "required": True,
                               "schema": {"type": "string"}}]}


def set_cookie(response, runtime, name, value, lifetime):
    response.set_cookie(name, value, max_age=lifetime, httponly=True,
                        secure=runtime.secure, samesite="lax", path="/")


def delete_cookie(response, runtime, name):
    response.delete_cookie(name, path="/", httponly=True, secure=runtime.secure, samesite="lax")


def origin_guard(request):
    origin = request.headers.get("origin")
    if origin is None:
        try:
            referer = urlsplit(request.headers.get("referer", ""))
        except ValueError:
            raise AuthError(403, "CSRF_INVALID", "Untrusted request origin.") from None
        origin = f"{referer.scheme}://{referer.netloc}" if referer.hostname else None
    if origin not in request.app.state.auth.settings.auth_allowed_origins:
        raise AuthError(403, "CSRF_INVALID", "Untrusted request origin.")


def guest_guard(request: Request):
    runtime = request.app.state.auth
    origin_guard(request)
    # Authenticated clients must logout before changing identity, using session-bound CSRF.
    if request.cookies.get("am_session"):
        raise AuthError(403, "CSRF_INVALID", "Logout before starting another authentication flow.")
    raw = runtime.pre_session(request.cookies.get(runtime.pre_cookie))
    runtime.verify_csrf(request.headers.get("x-csrf-token"), "pre:" + digest(raw))
    return raw


def current_session(db, runtime, raw, *, lock_user=True):
    if not raw or not TOKEN.fullmatch(raw):
        raise AuthError(401, "UNAUTHORIZED", "Invalid or expired session.")
    user_id = db.scalar(select(AuthSession.user_id).where(AuthSession.token_hash == digest(raw)))
    # Login/password changes lock user first; use that order everywhere to avoid lock inversion.
    user_stmt = select(User).where(User.id == user_id).execution_options(populate_existing=True)
    if lock_user:
        user_stmt = user_stmt.with_for_update()
    user = db.scalar(user_stmt) if user_id else None
    if user is None or user.status != "active":
        raise AuthError(401, "UNAUTHORIZED", "Invalid or expired session.")
    record = db.scalars(select(AuthSession).where(AuthSession.token_hash == digest(raw))
                        .with_for_update().execution_options(populate_existing=True)).one_or_none()
    now = runtime.now()
    if (record is None or record.revoked_at is not None or record.expires_at <= now
            or record.created_at > now or record.created_at + timedelta(seconds=ABSOLUTE_SECONDS) <= now):
        raise AuthError(401, "UNAUTHORIZED", "Invalid or expired session.")
    # Row lock serializes sliding expiry and revocation; expiry never moves backwards.
    record.expires_at = min(max(record.expires_at, now + timedelta(seconds=IDLE_SECONDS)),
                            record.created_at + timedelta(seconds=ABSOLUTE_SECONDS))
    return record


def user_private(db, user):
    profile = db.get(Profile, user.id)
    if profile is None:
        raise AuthError(500, "INTERNAL_ERROR", "Account data is unavailable.")
    roles = db.scalars(select(Role.code).join(UserRole).where(UserRole.user_id == user.id).order_by(Role.code)).all()
    return UserPrivate(id=user.id, username=user.username, email=user.email,
                       display_name=profile.display_name, roles=roles, status=user.status,
                       deleted_at=user.deleted_at)


@router.get("/csrf", response_model=CsrfResponse, operation_id="getCsrf",
            responses={status: ERRORS[status] for status in (422, 429, 500)})
def get_csrf(request: Request, response: Response):
    runtime = request.app.state.auth
    raw = request.cookies.get("am_session")
    if raw:
        try:
            with request.app.state.auth_session_factory() as db, db.begin():
                record = current_session(db, runtime, raw)
                binding = "session:" + str(record.id)
                lifetime = max(1, int((record.expires_at - runtime.now()).total_seconds()))
            set_cookie(response, runtime, "am_session", raw, lifetime)
            return CsrfResponse(csrf_token=runtime.csrf(binding))
        except AuthError as error:
            if error.status != 401:
                raise
            delete_cookie(response, runtime, "am_session")
    # This endpoint stays public: stale/missing pre-session receives a fresh one.
    pre = runtime.pre_session(request.cookies.get(runtime.pre_cookie), create=True)
    set_cookie(response, runtime, runtime.pre_cookie, pre, PRE_TTL)
    return CsrfResponse(csrf_token=runtime.csrf("pre:" + digest(pre)))


def _is_verification_required(email_service) -> bool:
    if email_service is not None:
        return bool(getattr(email_service.settings, "email_verification_required", False))
    from app.config import EmailSettings
    return bool(EmailSettings().email_verification_required)


def _require_available_email_service(email_service) -> None:
    if email_service is None or getattr(email_service.settings, "email_mode", "disabled") not in ("smtp", "sandbox"):
        raise AuthError(
            503,
            "EMAIL_SERVICE_UNAVAILABLE",
            "Dịch vụ email xác minh hiện không khả dụng. Vui lòng thử lại sau.",
        )


def _enforce_verification_rate_limits(runtime, request: Request, email: str) -> None:
    client_ip = request.client.host if request.client else "unknown"
    runtime.limiter.check(f"verification_email:ip:{client_ip}", 10, 600)
    runtime.limiter.check("verification_email:account:" + digest(email), 5, 600)


def _enforce_verification_cooldown(verif: AccountVerification, now: datetime) -> None:
    cooldown_target = verif.created_at + timedelta(seconds=30)
    if now < cooldown_target:
        remaining = max(1, int((cooldown_target - now).total_seconds()))
        raise AuthError(
            429,
            "RATE_LIMITED",
            f"Vui lòng đợi {remaining} giây trước khi gửi lại email xác minh.",
            retry_after=remaining,
            details={"next_open_at": cooldown_target.isoformat()},
        )


def _deliver_verification_email(
    email_service,
    *,
    to_email: str,
    display_name: str,
    raw_token: str,
    token_hash: str,
) -> None:
    from urllib.parse import urlencode
    base = email_service.settings.app_public_url.rstrip("/")
    verify_url = f"{base}/verify-email?{urlencode({'token': raw_token})}"
    email_res = email_service.send_account_verification_email(
        to_email=to_email,
        display_name=display_name,
        verify_url=verify_url,
        expires_hours=24,
        dedupe_key=f"verify:{token_hash}",
    )
    if email_res is None or email_res.status not in ("sent", "sandbox_captured"):
        raise AuthError(
            503,
            "EMAIL_DELIVERY_FAILED",
            "Không thể gửi email xác minh lúc này. Vui lòng thử lại sau.",
        )


@router.post("/register", response_model=UserPrivate | RegisterResponse, status_code=201, operation_id="register",
             responses={status: ERRORS[status] for status in (403, 409, 422, 429, 500)},
             openapi_extra=CSRF_HEADER)
def register(payload: RegisterInput, request: Request, pre=Depends(guest_guard)):
    runtime = request.app.state.auth
    encoded = runtime.hasher.hash(payload.password.get_secret_value())
    now, user_id = runtime.now(), uuid4()

    email_service = getattr(request.app.state, "email_service", None)
    verification_required = _is_verification_required(email_service)

    if verification_required:
        _require_available_email_service(email_service)
        _enforce_verification_rate_limits(runtime, request, str(payload.email))
        raw_token = secrets.token_urlsafe(32)
        token_hash = digest(raw_token)
        with request.app.state.auth_session_factory() as db, db.begin():
            if db.scalar(select(User.id).where(User.username == payload.username)) is not None:
                raise AuthError(409, "USERNAME_EXISTS", "Tag đã được sử dụng, vui lòng chọn tag khác.")
            if db.scalar(select(User.id).where(User.email == str(payload.email))) is not None:
                raise AuthError(409, "EMAIL_EXISTS", "Email đã được đăng ký, vui lòng đăng nhập.")
            pending_tag = db.scalar(
                select(AccountVerification.id).where(
                    AccountVerification.username == payload.username,
                    AccountVerification.email != str(payload.email),
                    AccountVerification.verified_at.is_(None),
                    AccountVerification.expires_at > now,
                )
            )
            if pending_tag is not None:
                raise AuthError(409, "USERNAME_EXISTS", "Tag đã được sử dụng, vui lòng chọn tag khác.")

            existing_verif = db.scalar(
                select(AccountVerification).where(AccountVerification.email == str(payload.email)).with_for_update()
            )
            if existing_verif is not None:
                _enforce_verification_cooldown(existing_verif, now)
                existing_verif.username = payload.username
                existing_verif.display_name = payload.display_name
                existing_verif.password_hash = encoded
                existing_verif.token_hash = token_hash
                existing_verif.created_at = now
                existing_verif.expires_at = now + timedelta(hours=24)
                existing_verif.verified_at = None
            else:
                db.add(
                    AccountVerification(
                        id=uuid4(),
                        email=str(payload.email),
                        username=payload.username,
                        display_name=payload.display_name,
                        password_hash=encoded,
                        token_hash=token_hash,
                        created_at=now,
                        expires_at=now + timedelta(hours=24),
                        verified_at=None,
                    )
                )

        _deliver_verification_email(
            email_service,
            to_email=str(payload.email),
            display_name=payload.display_name,
            raw_token=raw_token,
            token_hash=token_hash,
        )
        return RegisterResponse(
            status="pending_verification",
            email=str(payload.email),
            message="Email xác minh đã được gửi. Vui lòng kiểm tra hộp thư để kích hoạt tài khoản.",
            cooldown_seconds=30,
        )

    try:
        with request.app.state.auth_session_factory() as db, db.begin():
            from app.aura_lock import lock_aura_mutation
            lock_aura_mutation(db)
            now = runtime.now()
            # Unique code + ON CONFLICT handles simultaneous first registrations without ADMIN seed.
            db.execute(insert(Role).values(id=uuid4(), code="USER", description="User role")
                       .on_conflict_do_nothing(index_elements=[Role.code]))
            role_id = db.scalars(select(Role.id).where(Role.code == "USER")).one()
            user = User(id=user_id, username=payload.username, email=str(payload.email),
                        password_hash=encoded, status="active", created_at=now, updated_at=now)
            db.add(user)
            db.flush()
            db.add_all([Profile(user_id=user_id, display_name=payload.display_name, updated_at=now),
                        UserRole(user_id=user_id, role_id=role_id, granted_at=now)])
            db.flush()
            from app.aura_runtime import initialize_progress
            initialize_progress(db,user_id,now)
            result = user_private(db, user)
        return result
    except IntegrityError as error:
        diag = getattr(error.orig, "diag", None)
        cname = getattr(diag, "constraint_name", "") if diag else ""
        if "username" in cname:
            raise AuthError(409, "USERNAME_EXISTS", "Tag đã được sử dụng, vui lòng chọn tag khác.") from None
        if "email" in cname:
            raise AuthError(409, "EMAIL_EXISTS", "Email đã được đăng ký, vui lòng đăng nhập.") from None
        if getattr(error.orig, "sqlstate", None) == "23505":
            raise AuthError(409, "CONFLICT", "Username or email already registered.") from None
        raise


@router.post("/resend-verification", response_model=ResendVerificationResponse, operation_id="resendVerification",
             responses={status: ERRORS[status] for status in (400, 403, 409, 422, 429, 500)},
             openapi_extra=CSRF_HEADER)
def resend_verification(payload: ResendVerificationInput, request: Request, pre=Depends(guest_guard)):
    runtime = request.app.state.auth
    email_service = getattr(request.app.state, "email_service", None)
    _require_available_email_service(email_service)
    _enforce_verification_rate_limits(runtime, request, str(payload.email))

    now = runtime.now()
    raw_token = secrets.token_urlsafe(32)
    token_hash = digest(raw_token)

    with request.app.state.auth_session_factory() as db, db.begin():
        if db.scalar(select(User.id).where(User.email == str(payload.email))) is not None:
            raise AuthError(409, "ALREADY_REGISTERED", "Tài khoản đã được kích hoạt trước đó. Vui lòng đăng nhập.")

        verif = db.scalar(
            select(AccountVerification)
            .where(AccountVerification.email == str(payload.email), AccountVerification.verified_at.is_(None))
            .with_for_update()
        )
        if verif is None:
            raise AuthError(404, "NOT_FOUND", "Không tìm thấy yêu cầu xác minh cho email này. Vui lòng đăng ký tài khoản.")

        _enforce_verification_cooldown(verif, now)

        if verif.expires_at <= now:
            if db.scalar(select(User.id).where(User.username == verif.username)) is not None:
                raise AuthError(409, "USERNAME_EXISTS", "Tag đã được sử dụng, vui lòng đăng ký lại với tag khác.")
            pending_tag = db.scalar(
                select(AccountVerification.id).where(
                    AccountVerification.username == verif.username,
                    AccountVerification.email != str(payload.email),
                    AccountVerification.verified_at.is_(None),
                    AccountVerification.expires_at > now,
                )
            )
            if pending_tag is not None:
                raise AuthError(409, "USERNAME_EXISTS", "Tag đã được sử dụng, vui lòng đăng ký lại với tag khác.")

        verif.token_hash = token_hash
        verif.created_at = now
        verif.expires_at = now + timedelta(hours=24)
        display_name = verif.display_name

    _deliver_verification_email(
        email_service,
        to_email=str(payload.email),
        display_name=display_name,
        raw_token=raw_token,
        token_hash=token_hash,
    )
    return ResendVerificationResponse(
        status="sent",
        email=str(payload.email),
        message="Email xác minh đã được gửi lại.",
        cooldown_seconds=30,
    )


@router.post("/verify-email", response_model=VerifyEmailResponse, operation_id="verifyEmail",
             responses={status: ERRORS[status] for status in (400, 403, 409, 422, 429, 500)},
             openapi_extra=CSRF_HEADER)
def verify_email(payload: VerifyEmailInput, request: Request, pre=Depends(guest_guard)):
    runtime = request.app.state.auth
    client_ip = request.client.host if request.client else "unknown"
    runtime.limiter.check(f"verify_email:ip:{client_ip}", 20, 900)
    now = runtime.now()
    token_hash = digest(payload.token.strip())
    user_id = uuid4()
    with request.app.state.auth_session_factory() as db, db.begin():
        verif = db.scalar(
            select(AccountVerification)
            .where(AccountVerification.token_hash == token_hash)
            .with_for_update()
        )
        if verif is None or verif.verified_at is not None or verif.expires_at <= now:
            raise AuthError(400, "INVALID_VERIFICATION_TOKEN", "Liên kết xác minh không hợp lệ hoặc đã hết hạn.")

        existing = db.scalar(
            select(User.id).where((User.email == verif.email) | (User.username == verif.username))
        )
        if existing is not None:
            verif.verified_at = now
            raise AuthError(409, "ALREADY_REGISTERED", "Tài khoản đã được kích hoạt trước đó. Vui lòng đăng nhập.")

        from app.aura_lock import lock_aura_mutation
        from app.aura_runtime import initialize_progress
        lock_aura_mutation(db)

        db.execute(insert(Role).values(id=uuid4(), code="USER", description="User role")
                   .on_conflict_do_nothing(index_elements=[Role.code]))
        role_id = db.scalars(select(Role.id).where(Role.code == "USER")).one()
        user = User(
            id=user_id,
            username=verif.username,
            email=verif.email,
            password_hash=verif.password_hash,
            status="active",
            created_at=now,
            updated_at=now,
        )
        db.add(user)
        db.flush()
        db.add_all([
            Profile(user_id=user_id, display_name=verif.display_name, updated_at=now),
            UserRole(user_id=user_id, role_id=role_id, granted_at=now),
        ])
        db.flush()
        initialize_progress(db, user_id, now)
        verif.verified_at = now

    return VerifyEmailResponse(status="verified", message="Tài khoản của bạn đã được kích hoạt thành công!")


@router.post("/login", response_model=UserPrivate, operation_id="login", responses=ERRORS,
             openapi_extra=CSRF_HEADER)
def login(payload: LoginInput, request: Request, response: Response, pre=Depends(guest_guard)):
    runtime = request.app.state.auth
    runtime.limiter.check("account:" + digest(str(payload.email)), 10, 600)
    with request.app.state.auth_session_factory() as db, db.begin():
        user = db.scalars(select(User).where(User.email == str(payload.email)).with_for_update()).one_or_none()
        valid = runtime.verify_password(user.password_hash if user else runtime.dummy_hash, payload.password.get_secret_value())
        if not valid or user is None or user.status != "active":
            if user is None:
                pending_verif = db.scalar(
                    select(AccountVerification)
                    .where(AccountVerification.email == str(payload.email), AccountVerification.verified_at.is_(None))
                )
                if pending_verif is not None and pending_verif.expires_at > runtime.now():
                    raise AuthError(403, "ACCOUNT_UNVERIFIED", "Tài khoản chưa được xác minh email. Vui lòng kiểm tra hộp thư để kích hoạt.")
            raise AuthError(401, "UNAUTHORIZED", "Invalid email or password.")

        raw, now = secrets.token_urlsafe(32), runtime.now()
        db.add(AuthSession(id=uuid4(), user_id=user.id, token_hash=digest(raw), created_at=now,
                           expires_at=now + timedelta(seconds=IDLE_SECONDS)))
        if runtime.hasher.check_needs_rehash(user.password_hash):
            user.password_hash = runtime.hasher.hash(payload.password.get_secret_value())
        result = user_private(db, user)
        # Consume before commit: concurrent login with the same pre-session has only one winner.
        runtime.consume_pre(pre)
    set_cookie(response, runtime, "am_session", raw, IDLE_SECONDS)
    delete_cookie(response, runtime, runtime.pre_cookie)
    return result


@router.post("/logout", status_code=204, operation_id="logout", responses=ERRORS,
             openapi_extra=CSRF_HEADER)
def logout(request: Request, response: Response, raw=Depends(session_cookie)):
    runtime = request.app.state.auth
    with request.app.state.auth_session_factory() as db, db.begin():
        record = current_session(db, runtime, raw)
        origin_guard(request)
        runtime.verify_csrf(request.headers.get("x-csrf-token"), "session:" + str(record.id))
        record.revoked_at = runtime.now()
        session_id = str(record.id)
    presence = getattr(request.app.state, "presence", None)
    if presence is not None:
        presence.remove_session(session_id)
    delete_cookie(response, runtime, "am_session")

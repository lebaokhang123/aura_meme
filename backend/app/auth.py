"""P0 authentication: one PostgreSQL transaction per operation, no schema changes."""
from datetime import timedelta
import secrets
from urllib.parse import urlsplit
from uuid import uuid4

from fastapi import APIRouter, Depends, Request, Response
from fastapi.security import APIKeyCookie
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import IntegrityError

from app.auth_schemas import CsrfResponse, ErrorResponse, LoginInput, RegisterInput, UserPrivate
from app.models import AuthSession, Profile, Role, User, UserRole
from app.security import ABSOLUTE_SECONDS, IDLE_SECONDS, PRE_TTL, TOKEN, AuthError, digest


router = APIRouter(prefix="/api/v1/auth", tags=["Auth"])
session_cookie = APIKeyCookie(name="am_session", auto_error=False, scheme_name="sessionCookie")
ERRORS = {status: {"model": ErrorResponse} for status in (401, 403, 409, 422, 429, 500)}
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


def current_session(db, runtime, raw):
    if not raw or not TOKEN.fullmatch(raw):
        raise AuthError(401, "UNAUTHORIZED", "Invalid or expired session.")
    user_id = db.scalar(select(AuthSession.user_id).where(AuthSession.token_hash == digest(raw)))
    # Login/password changes lock user first; use that order everywhere to avoid lock inversion.
    user = db.scalar(select(User).where(User.id == user_id).with_for_update()
                     .execution_options(populate_existing=True)) if user_id else None
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
                       display_name=profile.display_name, roles=roles, status=user.status)


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


@router.post("/register", response_model=UserPrivate, status_code=201, operation_id="register",
             responses={status: ERRORS[status] for status in (403, 409, 422, 429, 500)},
             openapi_extra=CSRF_HEADER)
def register(payload: RegisterInput, request: Request, pre=Depends(guest_guard)):
    runtime = request.app.state.auth
    encoded = runtime.hasher.hash(payload.password.get_secret_value())
    now, user_id = runtime.now(), uuid4()
    try:
        with request.app.state.auth_session_factory() as db, db.begin():
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
            result = user_private(db, user)
        return result
    except IntegrityError as error:
        if getattr(error.orig, "sqlstate", None) == "23505":
            raise AuthError(409, "CONFLICT", "Username or email already registered.") from None
        raise


@router.post("/login", response_model=UserPrivate, operation_id="login", responses=ERRORS,
             openapi_extra=CSRF_HEADER)
def login(payload: LoginInput, request: Request, response: Response, pre=Depends(guest_guard)):
    runtime = request.app.state.auth
    runtime.limiter.check("account:" + digest(str(payload.email)), 10, 600)
    with request.app.state.auth_session_factory() as db, db.begin():
        user = db.scalars(select(User).where(User.email == str(payload.email)).with_for_update()).one_or_none()
        valid = runtime.verify_password(user.password_hash if user else runtime.dummy_hash, payload.password.get_secret_value())
        if not valid or user is None or user.status != "active":
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
    delete_cookie(response, runtime, "am_session")

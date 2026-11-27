from contextlib import asynccontextmanager
from typing import Literal

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session
from uuid import uuid4
from pydantic import BaseModel, ValidationError

from app.config import AuthSettings, ConfigurationError, EmailSettings, GoogleAuthSettings, PremiumSettings, VaultSettings, load_settings
from app.db import create_db_engine
from app.auth_schemas import CooldownDetails
from app.auth import router
from app.password_reset import router as password_reset_router
from app.google_auth import GoogleTokenVerifier, router as google_auth_router
from app.email_service import EmailService
from app.account import router as account_router
from app.profile_activity import router as profile_activity_router
from app.blog import router as blog_router
from app.media import router as media_router
from app.comments import router as comments_router
from app.admin_users import router as admin_users_router
from app.admin_posts import router as admin_posts_router
from app.admin_workspace import router as admin_workspace_router
from app.contact import router as contact_router
from app.own_posts import router as own_posts_router
from app.interactions import router as interactions_router
from app.comment_reactions import router as comment_reactions_router
from app.aura_reads import router as aura_reads_router
from app.checkin import router as checkin_router
from app.inventory import router as inventory_router
from app.vault import router as vault_router
from app.vault_open import router as vault_open_router
from app.vault_runtime import router as vault_runtime_router
from app.notifications import router as notifications_router
from app.presence import PresenceStore, router as presence_router
from app.premium import router as premium_router
from app.vnpay_adapter import VnpayAdapter
from app.paypal_adapter import PaypalAdapter
from app.security import AuthBoundaryMiddleware, AuthError, AuthRuntime


@asynccontextmanager
async def lifespan(app: FastAPI):
    engine = create_db_engine(load_settings())
    app.state.engine = engine
    try:
        try:
            app.state.auth = AuthRuntime(AuthSettings())
        except ValidationError:
            raise ConfigurationError("Invalid authentication configuration; check AUTH_SIGNING_KEY, AUTH_ENVIRONMENT and AUTH_ALLOWED_ORIGINS.") from None
        app.state.auth_session_factory = lambda: Session(engine)
        app.state.vault = VaultSettings()
        app.state.premium = PremiumSettings()
        secret = app.state.premium.vnpay_hash_secret.get_secret_value() if app.state.premium.vnpay_hash_secret else None
        app.state.vnpay = VnpayAdapter(
            tmn_code=app.state.premium.vnpay_tmn_code,
            hash_secret=secret,
            payment_url=app.state.premium.vnpay_payment_url,
            return_url=app.state.premium.vnpay_return_url,
            pricing_approved=app.state.premium.vnpay_pricing_approved,
        )
        paypal_secret = app.state.premium.paypal_client_secret.get_secret_value() if app.state.premium.paypal_client_secret else None
        app.state.paypal = PaypalAdapter(
            client_id=app.state.premium.paypal_client_id,
            client_secret=paypal_secret,
            mode=app.state.premium.paypal_mode,
            merchant_id=app.state.premium.paypal_merchant_id,
            webhook_id=app.state.premium.paypal_webhook_id,
            return_url=app.state.premium.paypal_return_url,
            cancel_url=app.state.premium.paypal_cancel_url,
        )
        app.state.google_auth = GoogleTokenVerifier(GoogleAuthSettings())
        app.state.email_service = EmailService(EmailSettings())
        app.state.presence = PresenceStore()
        yield
    finally:
        engine.dispose()


app = FastAPI(title="AuraMeme API", version="0.1.0", lifespan=lifespan)
app.include_router(router)
app.include_router(password_reset_router)
app.include_router(google_auth_router)
app.include_router(account_router)
app.include_router(profile_activity_router)
app.include_router(blog_router)
app.include_router(media_router)
app.include_router(comments_router)
app.include_router(admin_users_router)
app.include_router(admin_posts_router)
app.include_router(admin_workspace_router)
app.include_router(contact_router)
app.include_router(own_posts_router)
app.include_router(interactions_router)
app.include_router(comment_reactions_router)
app.include_router(aura_reads_router)
app.include_router(checkin_router)
app.include_router(inventory_router)
app.include_router(vault_router)
app.include_router(vault_open_router)
app.include_router(vault_runtime_router)
app.include_router(notifications_router)
app.include_router(presence_router)
app.include_router(premium_router)
app.add_middleware(AuthBoundaryMiddleware)


def error_response(status, code, message, retry_after=None, details=None):
    headers = {"Cache-Control": "no-store"}
    if retry_after:
        headers["Retry-After"] = str(retry_after)
    error = {"code": code, "message": message, "request_id": "req_" + uuid4().hex}
    if isinstance(details, dict) and isinstance(details.get("next_open_at"), str):
        try:
            error["details"] = CooldownDetails(next_open_at=details["next_open_at"]).model_dump(mode="json")
        except ValidationError:
            pass
    return JSONResponse(status_code=status, content={"error": error}, headers=headers)


@app.exception_handler(AuthError)
async def auth_error(request, error):
    return error_response(error.status, error.code, error.message, error.retry_after, error.details)


@app.exception_handler(RequestValidationError)
async def validation_error(request, error):
    # Pydantic errors can contain raw password input; never return or log that payload.
    return error_response(422, "VALIDATION_ERROR", "Invalid request data.")


@app.exception_handler(SQLAlchemyError)
async def database_error(request, error):
    return error_response(500, "INTERNAL_ERROR", "Database operation failed.")


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"
    if request.url.path.endswith("/receipt.pdf"):
        response.headers["X-Frame-Options"] = "SAMEORIGIN"
    else:
        response.headers["X-Frame-Options"] = "DENY"
    if request.url.path.startswith("/api/v1/auth/"):
        response.headers["Content-Security-Policy"] = "default-src 'none'; frame-ancestors 'none'"
    if request.url.scheme == "https" and request.app.state.auth.secure:
        response.headers["Strict-Transport-Security"] = "max-age=31536000"
    return response


class HealthResponse(BaseModel):
    status: Literal["ok"]


@app.get(
    "/health",
    response_model=HealthResponse,
    operation_id="health",
    summary="Health check (process readiness)",
    tags=["Health"],
)
def health() -> HealthResponse:
    return HealthResponse(status="ok")

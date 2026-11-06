from contextlib import asynccontextmanager
from typing import Literal

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session
from uuid import uuid4
from pydantic import BaseModel, ValidationError

from app.config import AuthSettings, ConfigurationError, load_settings
from app.db import create_db_engine
from app.auth import router
from app.account import router as account_router
from app.blog import router as blog_router
from app.media import router as media_router
from app.comments import router as comments_router
from app.admin_users import router as admin_users_router
from app.admin_posts import router as admin_posts_router
from app.contact import router as contact_router
from app.own_posts import router as own_posts_router
from app.interactions import router as interactions_router
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
        yield
    finally:
        engine.dispose()


app = FastAPI(title="AuraMeme API", version="0.1.0", lifespan=lifespan)
app.include_router(router)
app.include_router(account_router)
app.include_router(blog_router)
app.include_router(media_router)
app.include_router(comments_router)
app.include_router(admin_users_router)
app.include_router(admin_posts_router)
app.include_router(contact_router)
app.include_router(own_posts_router)
app.include_router(interactions_router)
app.add_middleware(AuthBoundaryMiddleware)


def error_response(status, code, message, retry_after=None):
    headers = {"Cache-Control": "no-store"}
    if retry_after:
        headers["Retry-After"] = str(retry_after)
    return JSONResponse(status_code=status, content={"error": {
        "code": code, "message": message, "request_id": "req_" + uuid4().hex,
    }}, headers=headers)


@app.exception_handler(AuthError)
async def auth_error(request, error):
    return error_response(error.status, error.code, error.message, error.retry_after)


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

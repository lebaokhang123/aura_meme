"""Database-backed session/RBAC dependencies, with one transaction per request."""
from dataclasses import dataclass

from fastapi import Depends, Request, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import current_session, origin_guard, session_cookie, set_cookie
from app.models import AuthSession, Role, User, UserRole
from app.security import AuthError


@dataclass
class AuthenticatedAccount:
    db: Session
    user: User
    session: AuthSession


def require_authenticated_user(request: Request, response: Response, raw=Depends(session_cookie)):
    runtime = request.app.state.auth
    with request.app.state.auth_session_factory() as db, db.begin():
        record = current_session(db, runtime, raw)
        lifetime = max(1, int((record.expires_at - runtime.now()).total_seconds()))
        set_cookie(response, runtime, "am_session", raw, lifetime)
        yield AuthenticatedAccount(db=db, user=db.get(User, record.user_id), session=record)
    # Callers use scope=function so commit errors cannot follow a successful response.


def require_account_csrf(request: Request, account=Depends(require_authenticated_user, scope="function")):
    origin_guard(request)
    request.app.state.auth.verify_csrf(request.headers.get("x-csrf-token"), "session:" + str(account.session.id))
    return account


def require_role(role: str):
    def check(account=Depends(require_authenticated_user, scope="function")):
        allowed = account.db.scalar(select(UserRole.user_id).join(Role).where(
            UserRole.user_id == account.user.id, Role.code == role))
        if allowed is None:
            raise AuthError(403, "FORBIDDEN", "Insufficient permissions.")
        return account
    return check

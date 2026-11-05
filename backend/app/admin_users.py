"""Admin-only account lifecycle; serialize role mutations before actor/target user locks."""
from typing import Literal
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Query, Request, Response
from pydantic import BaseModel, EmailStr, Field, field_validator
from sqlalchemy import delete, func, or_, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import IntegrityError

from app.auth import CSRF_HEADER, ERRORS, delete_cookie, session_cookie, user_private
from app.auth_schemas import LoginInput, RegisterInput, UserPrivate
from app.auth_schemas import ErrorResponse
from app.blog import page_rows
from app.blog_schemas import NonemptyPatch, Pagination, StrictInput
from app.models import AdminAuditLog, AuthSession, Profile, Role, User, UserRole
from app.permissions import authenticated_account, require_account_csrf, require_role
from app.security import AuthError, TOKEN


router = APIRouter(prefix="/api/v1/admin/users", tags=["Admin"])
NOT_FOUND = {404: {"model": ErrorResponse}}


class AdminCreateUser(RegisterInput, StrictInput):
    roles: list[Literal["USER", "ADMIN"]]


class AdminUserPatch(NonemptyPatch):
    status: Literal["active", "locked"] = None
    display_name: str = Field(default=None, min_length=1, max_length=80)
    email: EmailStr = None

    @field_validator("email", mode="before")
    @classmethod
    def normalized_email(cls, value):
        return LoginInput.normalize_email(value)

    @field_validator("display_name")
    @classmethod
    def nonblank_name(cls, value):
        return RegisterInput.nonempty_name(value)


class AdminUserPage(BaseModel):
    items: list[UserPrivate]
    pagination: Pagination


class AdminRolePatch(StrictInput):
    roles: list[Literal["USER", "ADMIN"]]


def require_admin_mutation(request: Request, response: Response, raw=Depends(session_cookie)):
    if not raw or not TOKEN.fullmatch(raw):
        raise AuthError(401, "UNAUTHORIZED", "Authentication required.")
    with request.app.state.auth_session_factory() as db, db.begin():
        # Lock before current_session locks the actor: mutual A->B changes must never hold opposing users first.
        db.scalar(select(Role.id).where(Role.code == "ADMIN").with_for_update())
        account = authenticated_account(request, response, raw, db)
        if db.scalar(select(UserRole.user_id).join(Role).where(UserRole.user_id == account.user.id,
                                                              Role.code == "ADMIN")) is None:
            raise AuthError(403, "FORBIDDEN", "Insufficient permissions.")
        yield require_account_csrf(request, account)


def user_state(db, user):
    return {"status": user.status, "roles": list(db.scalars(select(Role.code).join(UserRole).where(
        UserRole.user_id == user.id).order_by(Role.code)))}


def audit_user(account, user, action, before, now, **flags):
    account.db.add(AdminAuditLog(id=uuid4(), actor_id=account.user.id, action=action, target_type="user",
        target_id=str(user.id), before_json=before, after_json=user_state(account.db, user) | flags, created_at=now))
    account.db.flush()


def target_user(account, user_id):
    user = account.db.scalar(select(User).where(User.id == user_id, User.status != "deleted")
                             .with_for_update().execution_options(populate_existing=True))
    if user is None:
        raise AuthError(404, "NOT_FOUND", "User not found.")
    return user


def protect_last_admin(db, user, state):
    if user.status == "active" and "ADMIN" in state["roles"]:
        count = db.scalar(select(func.count()).select_from(UserRole).join(User).join(Role).where(
            Role.code == "ADMIN", User.status == "active"))
        if count <= 1:
            raise AuthError(409, "CONFLICT", "The last active administrator must remain active.")


def flush_identity(db):
    try:
        db.flush()
    except IntegrityError as error:
        if getattr(error.orig, "sqlstate", None) == "23505":
            raise AuthError(409, "CONFLICT", "Account identity already exists.") from None
        raise


def revoke_sessions(db, user_id, now):
    db.execute(update(AuthSession).where(AuthSession.user_id == user_id, AuthSession.revoked_at.is_(None))
               .values(revoked_at=now))


@router.get("", response_model=AdminUserPage, operation_id="adminListUsers",
            responses={status: ERRORS[status] for status in (401, 403, 422, 429, 500)})
def list_users(page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100),
               search: str | None = Query(None, max_length=100), status: str | None = None,
               account=Depends(require_role("ADMIN"))):
    if any(value is not None and "\x00" in value for value in (search, status)):
        raise AuthError(422, "VALIDATION_ERROR", "Invalid query text.")
    statement = select(User, Profile).join(Profile, Profile.user_id == User.id)
    if status is not None:
        statement = statement.where(User.status == status)
    if search is not None:
        statement = statement.where(or_(User.username.icontains(search, autoescape=True),
            User.email.icontains(search, autoescape=True), Profile.display_name.icontains(search, autoescape=True)))
    rows, pagination = page_rows(account.db, statement.order_by(User.username, User.id), page, page_size)
    roles = {user.id: [] for user, profile in rows}
    if rows:
        for user_id, code in account.db.execute(select(UserRole.user_id, Role.code).join(Role).where(
                UserRole.user_id.in_(roles)).order_by(Role.code)):
            roles[user_id].append(code)
    return AdminUserPage(items=[UserPrivate(id=user.id, username=user.username, email=user.email,
        display_name=profile.display_name, status=user.status, roles=roles[user.id]) for user, profile in rows], pagination=pagination)


@router.post("", status_code=201, response_model=UserPrivate, operation_id="adminCreateUser", responses=ERRORS,
             openapi_extra=CSRF_HEADER)
def create_user(payload: AdminCreateUser, request: Request, account=Depends(require_admin_mutation, scope="function")):
    now = request.app.state.auth.now()
    user = User(id=uuid4(), username=payload.username, email=str(payload.email),
        password_hash=request.app.state.auth.hasher.hash(payload.password.get_secret_value()), status="active",
        created_at=now, updated_at=now)
    account.db.add(user)
    flush_identity(account.db)
    account.db.add(Profile(user_id=user.id, display_name=payload.display_name, updated_at=now))
    for code in sorted(set(payload.roles)):
        account.db.execute(insert(Role).values(id=uuid4(), code=code, description=code + " role")
                           .on_conflict_do_nothing(index_elements=[Role.code]))
        role_id = account.db.scalar(select(Role.id).where(Role.code == code))
        account.db.add(UserRole(user_id=user.id, role_id=role_id, granted_at=now))
    account.db.flush()
    audit_user(account, user, "user.create", None, now)
    return user_private(account.db, user)


@router.patch("/{user_id}", response_model=UserPrivate, operation_id="adminSetUserStatus",
              responses=ERRORS | NOT_FOUND, openapi_extra=CSRF_HEADER)
def patch_user(user_id: UUID, payload: AdminUserPatch, request: Request, response: Response,
               account=Depends(require_admin_mutation, scope="function")):
    user = target_user(account, user_id)
    before = user_state(account.db, user)
    values = payload.model_dump(exclude_unset=True)
    if values.get("status") == "locked":
        protect_last_admin(account.db, user, before)
    changed = any(name in values and values[name] != getattr(user, name) for name in ("email", "status"))
    email_changed = "email" in values and values["email"] != user.email
    now = request.app.state.auth.now()
    for name, value in values.items():
        if name != "display_name": setattr(user, name, value)
    if "display_name" in values:
        profile = account.db.get(Profile, user.id)
        profile.display_name, profile.updated_at = values["display_name"], now
    user.updated_at = now
    flush_identity(account.db)
    if changed:
        revoke_sessions(account.db, user.id, now)
        if user.id == account.user.id: delete_cookie(response, request.app.state.auth, "am_session")
    audit_user(account, user, "user.update", before, now, email_changed=email_changed,
               profile_updated="display_name" in values)
    return user_private(account.db, user)


@router.delete("/{user_id}", status_code=204, operation_id="adminDeleteUser", responses=ERRORS | NOT_FOUND,
               openapi_extra=CSRF_HEADER)
def delete_user(user_id: UUID, request: Request, response: Response,
                account=Depends(require_admin_mutation, scope="function")):
    user = target_user(account, user_id)
    before = user_state(account.db, user)
    protect_last_admin(account.db, user, before)
    now = request.app.state.auth.now()
    user.status, user.deleted_at, user.updated_at = "deleted", now, now
    revoke_sessions(account.db, user.id, now)
    audit_user(account, user, "user.delete", before, now)
    if user.id == account.user.id: delete_cookie(response, request.app.state.auth, "am_session")


@router.put("/{user_id}/roles", response_model=UserPrivate, operation_id="adminSetUserRoles",
            responses=ERRORS | NOT_FOUND, openapi_extra=CSRF_HEADER)
def set_user_roles(user_id: UUID, payload: AdminRolePatch, request: Request, response: Response,
                   account=Depends(require_admin_mutation, scope="function")):
    user = target_user(account, user_id)
    before = user_state(account.db, user)
    requested, current = set(payload.roles), set(before["roles"])
    if "ADMIN" not in requested:
        protect_last_admin(account.db, user, before)
    now = request.app.state.auth.now()
    if requested != current:
        removed = select(Role.id).where(Role.code.in_(current - requested))
        account.db.execute(delete(UserRole).where(UserRole.user_id == user.id, UserRole.role_id.in_(removed)))
        for code in sorted(requested - current):
            account.db.execute(insert(Role).values(id=uuid4(), code=code, description=code + " role")
                               .on_conflict_do_nothing(index_elements=[Role.code]))
            role_id = account.db.scalar(select(Role.id).where(Role.code == code))
            account.db.add(UserRole(user_id=user.id, role_id=role_id, granted_at=now))
        user.updated_at = now
        account.db.flush()
        revoke_sessions(account.db, user.id, now)
        if user.id == account.user.id:
            delete_cookie(response, request.app.state.auth, "am_session")
    audit_user(account, user, "user.roles", before, now, roles_changed=requested != current)
    return user_private(account.db, user)

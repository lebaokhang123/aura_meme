"""Account profile and password APIs; schema and admin CRUD are outside M2.2."""
from fastapi import APIRouter, Depends, Path, Request
from sqlalchemy import select, update

from app.account_schemas import AccountPrivate, PasswordChange, ProfilePatch, PublicProfile
from app.auth import CSRF_HEADER, ERRORS, user_private
from app.auth_schemas import ErrorResponse
from app.models import AuthSession, Profile, User
from app.permissions import require_account_csrf, require_authenticated_user
from app.security import AuthError
from app.media import media_url


router = APIRouter(prefix="/api/v1/users", tags=["Account"])
PROFILE_FIELDS = ("birth_year", "address", "phone", "bio", "avatar_media_id", "cover_media_id")


def private_profile(account):
    basic = user_private(account.db, account.user)
    profile = account.db.get(Profile, account.user.id)
    return AccountPrivate(**basic.model_dump(), **{name: getattr(profile, name) for name in PROFILE_FIELDS},
                          avatar_url=profile.avatar_url, cover_url=media_url(profile.cover_media_id))


@router.get("/me", response_model=AccountPrivate, operation_id="getMe",
            responses={status: ERRORS[status] for status in (401, 403, 422, 429, 500)})
def get_me(account=Depends(require_authenticated_user, scope="function")):
    return private_profile(account)


@router.patch("/me", response_model=AccountPrivate, operation_id="updateMe", responses=ERRORS,
              openapi_extra=CSRF_HEADER)
def update_me(payload: ProfilePatch, request: Request, account=Depends(require_account_csrf)):
    values = payload.model_dump(exclude_unset=True)
    if values.get("birth_year") is not None and values["birth_year"] > request.app.state.auth.now().year:
        raise AuthError(422, "VALIDATION_ERROR", "Birth year must not be in the future.")
    profile = account.db.get(Profile, account.user.id)
    if profile is None:
        raise AuthError(500, "INTERNAL_ERROR", "Account data is unavailable.")
    for name, value in values.items():
        setattr(profile, name, value)
    profile.updated_at = request.app.state.auth.now()
    account.db.flush()
    return private_profile(account)


@router.put("/me/password", status_code=204, operation_id="changePassword", responses=ERRORS,
            openapi_extra=CSRF_HEADER)
def change_password(payload: PasswordChange, request: Request, account=Depends(require_account_csrf)):
    runtime = request.app.state.auth
    runtime.limiter.check("password:" + str(account.user.id), 5, 600)
    if not runtime.verify_password(account.user.password_hash, payload.current_password.get_secret_value()):
        raise AuthError(403, "FORBIDDEN", "Current password is incorrect.")
    account.user.password_hash = runtime.hasher.hash(payload.new_password.get_secret_value())
    account.user.updated_at = runtime.now()
    account.db.execute(update(AuthSession).where(
        AuthSession.user_id == account.user.id, AuthSession.id != account.session.id,
        AuthSession.revoked_at.is_(None)).values(revoked_at=runtime.now()))


@router.get("/{username}", response_model=PublicProfile, operation_id="getPublicUser",
            responses={status: {"model": ErrorResponse} for status in (404, 422, 429, 500)})
def get_public_user(request: Request, username: str = Path(min_length=3, max_length=32, pattern=r"^[a-z0-9_]+$")):
    with request.app.state.auth_session_factory() as db:
        row = db.execute(select(User, Profile).join(Profile, Profile.user_id == User.id).where(
            User.username == username, User.status == "active")).one_or_none()
        if row is None:
            raise AuthError(404, "NOT_FOUND", "Profile not found.")
        user, profile = row
        return PublicProfile(id=user.id, username=user.username, display_name=profile.display_name,
                          created_at=user.created_at, bio=profile.bio, avatar_url=profile.avatar_url)

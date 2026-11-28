"""Account profile and password APIs; schema and admin CRUD are outside M2.2."""
from uuid import uuid4
from fastapi import APIRouter, Depends, Path, Query, Request
from sqlalchemy import case, delete, exists, func, or_, select, update

from app.account_schemas import AccountPrivate, FollowResult, PasswordChange, ProfilePatch, PublicProfile, PublicUserSearchPage, SearchPagination, UserPublic
from app.auth import CSRF_HEADER, ERRORS, session_cookie, user_private
from app.auth_schemas import ErrorResponse
from app.models import AuthSession, Profile, User, UserFollow
from app.permissions import require_account_csrf, require_authenticated_user
from app.security import AuthError
from app.media import media_url
from app.notifications import create_notification


router = APIRouter(prefix="/api/v1/users", tags=["Account"])
PROFILE_FIELDS = ("birth_year", "address", "phone", "bio", "avatar_media_id", "cover_media_id")


def private_profile(account):
    from app.aura_v1 import admin_cosmetic_title
    basic = user_private(account.db, account.user)
    profile = account.db.get(Profile, account.user.id)
    return AccountPrivate(**basic.model_dump(), **{name: getattr(profile, name) for name in PROFILE_FIELDS},
                          avatar_url=profile.avatar_url, cover_url=media_url(profile.cover_media_id),
                          title=admin_cosmetic_title("ADMIN" in basic.roles))


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


@router.get("", response_model=PublicUserSearchPage, operation_id="searchUsersRoot",
            responses={status: {"model": ErrorResponse} for status in (422, 429, 500)})
@router.get("/search", response_model=PublicUserSearchPage, operation_id="searchPublicUsers",
            responses={status: {"model": ErrorResponse} for status in (422, 429, 500)})
def search_public_users(request: Request, q: str | None = Query(None, max_length=100),
                        search: str | None = Query(None, max_length=100),
                        page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=50)):
    query_str = q if q is not None else search
    if query_str is not None and "\x00" in query_str:
        raise AuthError(422, "VALIDATION_ERROR", "Invalid query text.")
    clean_q = (query_str or "").strip()
    from app.blog_schemas import Pagination
    if not clean_q:
        return PublicUserSearchPage(items=[], pagination=Pagination(page=page, page_size=page_size, total=0, total_pages=0))

    username_query = clean_q.lstrip("@").lower()
    from app.blog import search_text, searchable, page_rows
    from app.aura_runtime import public_is_admin_column, public_level_column
    from app.membership import read_users_membership_tiers

    now = request.app.state.auth.now()
    term = search_text(clean_q)

    with request.app.state.auth_session_factory() as db:
        statement = (
            select(User, Profile, public_level_column(now), public_is_admin_column())
            .join(Profile, Profile.user_id == User.id)
            .where(
                User.status == "active",
                or_(
                    User.username.contains(username_query),
                    searchable(Profile.display_name).contains(term, autoescape=True),
                ),
            )
            .order_by(
                case((User.username == username_query, 1), else_=2),
                User.created_at.desc(),
                User.id.desc(),
            )
        )
        rows, pagination = page_rows(db, statement, page, page_size)
        user_ids = {u.id for u, p, lvl, adm in rows}
        tiers = read_users_membership_tiers(db, user_ids, now) if user_ids else {}

        items = [
            UserPublic(
                id=u.id,
                username=u.username,
                display_name=p.display_name,
                created_at=u.created_at,
                bio=p.bio,
                avatar_url=p.avatar_url,
                level=lvl,
                membership_tier=tiers.get(u.id, "free"),
                is_admin_title=bool(adm),
            )
            for u, p, lvl, adm in rows
        ]
        return PublicUserSearchPage(items=items, pagination=SearchPagination(**pagination.model_dump()))


@router.get("/{username}", response_model=PublicProfile, operation_id="getPublicUser",
            responses={status: {"model": ErrorResponse} for status in (404, 422, 429, 500)})
def get_public_user(request: Request, username: str = Path(min_length=3, max_length=32, pattern=r"^[a-z0-9_]+$"),
                    raw: str | None = Depends(session_cookie)):
    with request.app.state.auth_session_factory() as db:
        from app.aura_runtime import public_is_admin_column, public_level_column
        row = db.execute(select(User, Profile, public_level_column(request.app.state.auth.now()), public_is_admin_column()).join(
            Profile, Profile.user_id == User.id).where(User.username == username, User.status == "active")).one_or_none()
        if row is None:
            raise AuthError(404, "NOT_FOUND", "Profile not found.")
        user, profile, level, is_admin = row
        from app.membership import read_users_membership_tiers
        from app.models import AssetItem, UserEquipment, UserInventory
        from app.catalog_rights import reviewed_source_rights_sql
        from sqlalchemy import and_
        now = request.app.state.auth.now()
        tiers = read_users_membership_tiers(db, {user.id}, now)
        membership_tier = tiers.get(user.id, "free")
        bg_effect = db.scalar(
            select(AssetItem.effect_key)
            .select_from(UserEquipment)
            .join(AssetItem, AssetItem.id == UserEquipment.asset_id)
            .join(
                UserInventory,
                and_(
                    UserInventory.user_id == UserEquipment.user_id,
                    UserInventory.asset_id == UserEquipment.asset_id,
                ),
            )
            .where(
                UserEquipment.user_id == user.id,
                UserEquipment.slot_kind == "background",
                AssetItem.kind == "background",
                UserInventory.quantity > 0,
                AssetItem.active.is_(True),
                reviewed_source_rights_sql(AssetItem.source_rights),
            )
        )

        follower_count = int(db.scalar(
            select(func.count(UserFollow.follower_id)).where(UserFollow.followee_id == user.id)
        ) or 0)

        viewer_id = None
        if raw:
            try:
                from app.auth import current_session
                sess_record = current_session(db, request.app.state.auth, raw)
                viewer_id = sess_record.user_id
            except Exception:
                viewer_id = None

        is_following = bool(
            db.scalar(
                select(
                    exists().where(
                        UserFollow.follower_id == viewer_id,
                        UserFollow.followee_id == user.id,
                    )
                )
            )
        ) if viewer_id else False

        return PublicProfile(id=user.id, username=user.username, display_name=profile.display_name,
                          created_at=user.created_at, bio=profile.bio, avatar_url=profile.avatar_url,
                          level=level, membership_tier=membership_tier, is_admin_title=bool(is_admin),
                          equipped_background_effect=bg_effect,
                          follower_count=follower_count, is_following=is_following)


@router.post("/{username}/follow", response_model=FollowResult, operation_id="followUser",
             responses=ERRORS | {404: {"model": ErrorResponse}}, openapi_extra=CSRF_HEADER)
def follow_user(request: Request, username: str = Path(min_length=3, max_length=32, pattern=r"^[a-z0-9_]+$"),
                account=Depends(require_account_csrf)):
    now = request.app.state.auth.now()
    db = account.db
    target_user = db.scalar(
        select(User).where(User.username == username, User.status == "active").with_for_update()
    )
    if target_user is None:
        raise AuthError(404, "NOT_FOUND", "User not found.")
    if target_user.id == account.user.id:
        raise AuthError(400, "INVALID_ACTION", "You cannot follow yourself.")

    # Idempotent follow insertion
    existing = db.scalar(
        select(UserFollow).where(
            UserFollow.follower_id == account.user.id,
            UserFollow.followee_id == target_user.id,
        ).with_for_update()
    )
    if existing is None:
        db.add(UserFollow(follower_id=account.user.id, followee_id=target_user.id, created_at=now))
        db.flush()
        create_notification(
            db,
            recipient_user_id=target_user.id,
            actor_user_id=account.user.id,
            type="follow",
            target_type="user",
            target_id=account.user.id,
            payload={"follower_username": account.user.username},
            dedupe_key=f"follow:{account.user.id}:{target_user.id}",
            now=now,
        )

        # Award +10 EXP to target_user once in history (anti-farm)
        event_key = f"follow-v1:{account.user.id}"
        from app.models import AuraLedger, RewardPolicyVersion
        already_rewarded = db.scalar(
            select(AuraLedger.id).where(
                AuraLedger.user_id == target_user.id,
                AuraLedger.event_key == event_key,
            )
        )
        if already_rewarded is None:
            policy = db.scalar(
                select(RewardPolicyVersion)
                .where(RewardPolicyVersion.status == "published", RewardPolicyVersion.effective_at <= now)
                .order_by(RewardPolicyVersion.effective_at.desc())
            )
            if policy is not None:
                from app.aura_runtime import _state, _updated
                state = _state(db, target_user.id, now, initialize=True, locked=True)
                db.add(AuraLedger(
                    id=uuid4(),
                    user_id=target_user.id,
                    event_key=event_key,
                    event_type="adjustment",
                    source_actor_id=account.user.id,
                    source_post_id=None,
                    source_comment_id=None,
                    policy_id=policy.id,
                    base_xp=10,
                    bonus_xp=0,
                    tier_at_event="FREE",
                    multiplier_at_event=1,
                    reverses_id=None,
                    occurred_at=now,
                ))
                db.flush()
                _updated(db, state, 10, 0, now)

    count = int(db.scalar(
        select(func.count(UserFollow.follower_id)).where(UserFollow.followee_id == target_user.id)
    ) or 0)
    return FollowResult(follower_count=count, is_following=True)


@router.delete("/{username}/follow", response_model=FollowResult, operation_id="unfollowUser",
               responses=ERRORS | {404: {"model": ErrorResponse}}, openapi_extra=CSRF_HEADER)
def unfollow_user(request: Request, username: str = Path(min_length=3, max_length=32, pattern=r"^[a-z0-9_]+$"),
                  account=Depends(require_account_csrf)):
    db = account.db
    target_user = db.scalar(
        select(User).where(User.username == username, User.status == "active").with_for_update()
    )
    if target_user is None:
        raise AuthError(404, "NOT_FOUND", "User not found.")

    db.execute(
        delete(UserFollow).where(
            UserFollow.follower_id == account.user.id,
            UserFollow.followee_id == target_user.id,
        )
    )
    db.flush()

    count = int(db.scalar(
        select(func.count(UserFollow.follower_id)).where(UserFollow.followee_id == target_user.id)
    ) or 0)
    return FollowResult(follower_count=count, is_following=False)

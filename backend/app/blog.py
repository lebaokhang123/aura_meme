"""Categories/audit and author-owned posts; no renderer/storage/moderation."""
import unicodedata
from typing import Literal
from uuid import UUID, uuid4
from fastapi import APIRouter, Depends, Query, Request, Response
from sqlalchemy import exists, func, or_, select
from sqlalchemy.exc import IntegrityError
from app.account_schemas import UserPublic
from app.auth import CSRF_HEADER, ERRORS, session_cookie
from app.auth_schemas import ErrorResponse
from app.blog_schemas import CategoryFeedItem, CategoryFeedPage, CategoryInput, CategoryPage, CategoryPatch, CategoryResponse, Pagination, PostInput, PostPage, PostPatch, PostResponse
from app.models import AdminAuditLog, Category, MediaUpload, Post, PostReaction, Profile, User
from app.media import media_url
from app.permissions import optional_account_reader, require_account_csrf, require_role
from app.security import AuthError

router = APIRouter(prefix="/api/v1", tags=["Blog"])


def feed_reader(request:Request,response:Response,include_interactions:bool=False,raw=Depends(session_cookie)):
    if include_interactions:
        yield from optional_account_reader(request,response,raw)
    else:
        # Legacy public reads remain public; only personalized counters require a valid supplied session.
        with request.app.state.auth_session_factory() as db:yield db,None

def technical_title(content):
    return next((line.strip()[:160] for line in content.splitlines() if line.strip()), "Ảnh/GIF")

def search_text(value):
    return "".join(c for c in unicodedata.normalize("NFD", value.lower().replace("đ","d")) if not 0x300<=ord(c)<=0x36f)

_ACCENTS={chr(n):search_text(chr(n)) for n in [*range(0xc0,0x250),*range(0x1e00,0x1f00)] if len(search_text(chr(n)))==1 and search_text(chr(n)) in "abcdefghijklmnopqrstuvwxyz"}
def searchable(column):
    return func.translate(func.translate(func.lower(column),"".join(_ACCENTS),"".join(_ACCENTS.values())), "".join(chr(n) for n in range(0x300,0x370)), "")

def page_rows(db, statement, page, size):
    total = db.scalar(select(func.count()).select_from(statement.order_by(None).subquery()))
    offset = (page - 1) * size
    # Out-of-range pages never reach PostgreSQL OFFSET (which is bounded by bigint).
    rows = db.execute(statement.offset(offset).limit(size)).all() if offset < total else []
    return rows, Pagination(page=page, page_size=size, total=total, total_pages=(total + size - 1) // size)


def category_dto(category):
    return CategoryResponse.model_validate(category, from_attributes=True)


def category_list(db, statement, page, size, sort="slug_asc"):
    ordering = {"slug_asc": (Category.slug, Category.id), "name_asc": (Category.name, Category.id),
                "name_desc": (Category.name.desc(), Category.id.desc())}
    rows, pagination = page_rows(db, statement.order_by(*ordering[sort]), page, size)
    return CategoryPage(items=[category_dto(row[0]) for row in rows], pagination=pagination)


def require_admin_csrf(request: Request, account=Depends(require_role("ADMIN"))):
    return require_account_csrf(request, account)


def category_snapshot(category):
    return category_dto(category).model_dump(mode="json") | {
        "created_at": category.created_at.isoformat(), "updated_at": category.updated_at.isoformat()}


def audit_category(account, category, action, before, now):
    account.db.add(AdminAuditLog(id=uuid4(), actor_id=account.user.id, action=action,
        target_type="category", target_id=str(category.id), before_json=before,
        after_json=category_snapshot(category), created_at=now))
    account.db.flush()


def locked_category(db, category_id, active=False):
    query = select(Category).where(Category.id == category_id)
    if active:
        query = query.where(Category.status == "active")
    category = db.scalar(query.with_for_update(read=active).execution_options(populate_existing=True))
    if category is None:
        raise AuthError(422 if active else 404, "VALIDATION_ERROR" if active else "NOT_FOUND",
                        "An active category is required." if active else "Category not found.")
    return category


@router.get("/categories", response_model=CategoryFeedPage, operation_id="listCategories",
            responses={s: ERRORS[s] for s in (422, 429, 500)})
def list_categories(request: Request, page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100),
                    search: str | None = Query(None, max_length=100), slug: str | None = None,
                    sort: Literal["slug_asc", "name_asc", "name_desc"] = "slug_asc"):
    if any(value is not None and "\x00" in value for value in (search, slug)):
        raise AuthError(422, "VALIDATION_ERROR", "Invalid query text.")
    statement = select(Category).where(Category.status == "active")
    if search is not None:
        statement = statement.where(or_(Category.name.icontains(search, autoescape=True), Category.slug.icontains(search, autoescape=True)))
    if slug is not None:
        statement = statement.where(Category.slug == slug)
    with request.app.state.auth_session_factory() as db:
        result=category_list(db, statement, page, page_size, sort)
        counts=dict(db.execute(public_posts().with_only_columns(Post.category_id,func.count()).group_by(Post.category_id)).all())
        return CategoryFeedPage(items=[CategoryFeedItem(**item.model_dump(),post_count=counts.get(item.id,0)) for item in result.items],pagination=result.pagination)


@router.get("/admin/categories", response_model=CategoryPage, operation_id="adminListCategories", tags=["Admin"],
            responses={s: ERRORS[s] for s in (401, 403, 422, 429, 500)})
def admin_list_categories(page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100),
                          search: str | None = Query(None, max_length=100), status: str | None = None,
                          sort: Literal["slug_asc", "name_asc", "name_desc"] = "slug_asc",
                          account=Depends(require_role("ADMIN"))):
    if any(value is not None and "\x00" in value for value in (search, status)):
        raise AuthError(422, "VALIDATION_ERROR", "Invalid query text.")
    statement = select(Category)
    if status is not None:
        statement = statement.where(Category.status == status)
    if search is not None:
        statement = statement.where(or_(Category.name.icontains(search, autoescape=True), Category.slug.icontains(search, autoescape=True)))
    return category_list(account.db, statement, page, page_size, sort)


@router.post("/admin/categories", response_model=CategoryResponse, status_code=201,
             operation_id="adminCreateCategory", tags=["Admin"], responses=ERRORS, openapi_extra=CSRF_HEADER)
def admin_create_category(payload: CategoryInput, request: Request, account=Depends(require_admin_csrf)):
    now = request.app.state.auth.now()
    category = Category(id=uuid4(), name=payload.name, slug=payload.slug, status="active", created_at=now, updated_at=now)
    account.db.add(category)
    try:
        account.db.flush()
    except IntegrityError as error:
        if getattr(error.orig, "sqlstate", None) == "23505":
            raise AuthError(409, "CONFLICT", "Category slug already exists.") from None
        raise
    audit_category(account, category, "category.create", None, now)
    return category_dto(category)


@router.patch("/admin/categories/{category_id}", response_model=CategoryResponse, operation_id="adminUpdateCategory",
              tags=["Admin"], responses=ERRORS | {404: {"model": ErrorResponse}}, openapi_extra=CSRF_HEADER)
def admin_update_category(category_id: UUID, payload: CategoryPatch, request: Request, account=Depends(require_admin_csrf)):
    category = locked_category(account.db, category_id)
    before = category_snapshot(category)
    for name, value in payload.model_dump(exclude_unset=True).items():
        setattr(category, name, value)
    category.updated_at = request.app.state.auth.now()
    audit_category(account, category, "category.update", before, category.updated_at)
    return category_dto(category)


@router.delete("/admin/categories/{category_id}", status_code=204, operation_id="adminDeleteCategory",
               tags=["Admin"], responses=ERRORS | {404: {"model": ErrorResponse}}, openapi_extra=CSRF_HEADER)
def admin_delete_category(category_id: UUID, request: Request, account=Depends(require_admin_csrf)):
    category = locked_category(account.db, category_id)
    before = category_snapshot(category)
    category.status, category.updated_at = "hidden", request.app.state.auth.now()
    audit_category(account, category, "category.hide", before, category.updated_at)


def public_posts():
    ready = exists(select(MediaUpload.id).where(MediaUpload.id == Post.media_id,
        MediaUpload.owner_id == Post.author_id, MediaUpload.status == "ready"))
    return select(Post, User, Profile, Category).join(User, User.id == Post.author_id).join(
        Profile, Profile.user_id == User.id).join(Category, Category.id == Post.category_id).where(
        Post.status == "published", Post.deleted_at.is_(None), User.status == "active",
        Category.status == "active", or_(Post.media_id.is_(None), ready))


def post_dto(post, user, profile, category):
    author = UserPublic(id=user.id, username=user.username, display_name=profile.display_name,
        bio=profile.bio, created_at=user.created_at, avatar_url=profile.avatar_url)
    # comments_count is optional and omitted until a real aggregate is requested.
    return PostResponse(id=post.id, author=author, category=category_dto(category), title=post.title,
        content=post.content, status=post.status, created_at=post.created_at, updated_at=post.updated_at, media_url=media_url(post.media_id))


def validate_post(db, user_id, category_id, media_id, content, *, allow_hidden_category=False):
    category = locked_category(db, category_id, active=not allow_hidden_category)
    if media_id is not None:
        media = db.scalar(select(MediaUpload).where(MediaUpload.id == media_id, MediaUpload.owner_id == user_id).with_for_update())
        if media is None or media.status != "ready":
            raise AuthError(422, "VALIDATION_ERROR", "Media must be ready and owned by the author.")
    if not content.strip() and media_id is None:
        raise AuthError(422, "VALIDATION_ERROR", "Content or valid media is required.")
    return category


@router.get("/posts", response_model=PostPage, operation_id="listPosts",
            responses={s: ERRORS[s] for s in (401, 422, 429, 500)},
            openapi_extra={"security":[{},{"sessionCookie":[]}]})
def list_posts(request: Request, page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100),
               search: str | None = Query(None, max_length=100), category: str | None = None,
               author: str | None = Query(None, max_length=32),
               sort: Literal["created_desc", "created_asc", "title_asc", "reaction_desc"] = "created_desc",
               include_interactions: bool = False, reader=Depends(feed_reader,scope="function")):
    if any(value is not None and "\x00" in value for value in (search, category, author)):
        raise AuthError(422, "VALIDATION_ERROR", "Invalid query text.")
    statement = public_posts()
    if search is not None:
        statement = statement.where(or_(searchable(Post.title).contains(search_text(search), autoescape=True), searchable(Post.content).contains(search_text(search), autoescape=True)))
    if category is not None:
        statement = statement.where(Category.slug == category)
    if author is not None:
        statement = statement.where(User.username == author)
    score=select(func.count()).select_from(PostReaction).join(User,User.id==PostReaction.user_id).where(PostReaction.post_id==Post.id,User.status=="active").correlate(Post).scalar_subquery()
    ordering = {"reaction_desc": (score.desc(),Post.created_at.desc(),Post.id.desc()),
                "created_desc": (Post.created_at.desc(), Post.id.desc()),
                "created_asc": (Post.created_at, Post.id), "title_asc": (Post.title, Post.id)}
    db,viewer_id=reader
    rows, pagination = page_rows(db, statement.order_by(*ordering[sort]), page, page_size)
    items=[]
    for row in rows:
        dto=post_dto(*row)
        if include_interactions:
            from app.interactions import get_post_interactions
            try:dto.interactions=get_post_interactions(dto.id,reader=(db,viewer_id))
            except AuthError as error:
                if error.status==404:continue
                raise
        items.append(dto)
    return PostPage(items=items,pagination=pagination)


@router.post("/posts", response_model=PostResponse, status_code=201, operation_id="createPost",
             responses=ERRORS, openapi_extra=CSRF_HEADER)
def create_post(payload: PostInput, request: Request, account=Depends(require_account_csrf)):
    values=payload.model_dump(exclude={"request_id"})
    values["title"]=payload.title if payload.title is not None else technical_title(payload.content)
    if payload.request_id is not None:
        existing=account.db.get(Post,payload.request_id)
        if existing is not None:
            if existing.author_id!=account.user.id or existing.deleted_at is not None or any(getattr(existing,k)!=v for k,v in values.items()):
                raise AuthError(409,"CONFLICT","Request ID already used.")
            category=validate_post(account.db,account.user.id,existing.category_id,existing.media_id,existing.content)
            return post_dto(existing,account.user,account.db.get(Profile,account.user.id),category)
    category = validate_post(account.db, account.user.id, payload.category_id, payload.media_id, payload.content)
    now = request.app.state.auth.now()
    post = Post(id=payload.request_id or uuid4(), author_id=account.user.id, created_at=now, updated_at=now, **values)
    account.db.add(post)
    try:account.db.flush()
    except IntegrityError as error:
        if getattr(error.orig,"sqlstate",None)=="23505":raise AuthError(409,"CONFLICT","Request ID already used.") from None
        raise
    return post_dto(post, account.user, account.db.get(Profile, account.user.id), category)


@router.get("/posts/{post_id}", response_model=PostResponse, operation_id="getPost",
            responses={s: {"model": ErrorResponse} for s in (404, 422, 429, 500)})
def get_post(post_id: UUID, request: Request):
    with request.app.state.auth_session_factory() as db:
        row = db.execute(public_posts().where(Post.id == post_id)).one_or_none()
        if row is None:
            raise AuthError(404, "NOT_FOUND", "Post not found.")
        return post_dto(*row)


def owned_post(db, user_id, post_id, editing=False):
    statement = select(Post).where(Post.id == post_id, Post.author_id == user_id, Post.status != "deleted")
    if editing:
        statement = statement.where(Post.status.in_(["draft", "published"]))
    post = db.scalar(statement.with_for_update().execution_options(populate_existing=True))
    if post is None:
        raise AuthError(404, "NOT_FOUND", "Post not found.")
    return post


@router.patch("/posts/{post_id}", response_model=PostResponse, operation_id="updatePost",
              responses=ERRORS | {404: {"model": ErrorResponse}}, openapi_extra=CSRF_HEADER)
def update_post(post_id: UUID, payload: PostPatch, request: Request, account=Depends(require_account_csrf)):
    post = owned_post(account.db, account.user.id, post_id, editing=True)
    values = payload.model_dump(exclude_unset=True)
    if "content" in values and "title" not in values and post.title==technical_title(post.content):values["title"]=technical_title(values["content"])
    category = validate_post(account.db, account.user.id, values.get("category_id", post.category_id),
                             values.get("media_id", post.media_id), values.get("content", post.content))
    for name, value in values.items():
        setattr(post, name, value)
    post.updated_at = request.app.state.auth.now()
    account.db.flush()
    return post_dto(post, account.user, account.db.get(Profile, account.user.id), category)


@router.delete("/posts/{post_id}", status_code=204, operation_id="deletePost",
               responses=ERRORS | {404: {"model": ErrorResponse}}, openapi_extra=CSRF_HEADER)
def delete_post(post_id: UUID, request: Request, account=Depends(require_account_csrf)):
    post = owned_post(account.db, account.user.id, post_id)
    post.status, post.deleted_at = "deleted", request.app.state.auth.now()
    post.updated_at = post.deleted_at

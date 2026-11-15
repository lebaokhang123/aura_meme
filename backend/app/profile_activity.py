"""Read-only public post/comment counts on the Vietnam calendar."""
from datetime import date, datetime, time, timedelta
from typing import Literal
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Path, Request
from pydantic import BaseModel, Field
from sqlalchemy import Date, func, select

from app.auth_schemas import ErrorResponse
from app.blog import public_posts
from app.models import Comment, Post, Profile, User
from app.security import AuthError

router = APIRouter(prefix="/api/v1/users", tags=["Account"])
TIMEZONE = "Asia/Ho_Chi_Minh"


class ActivityDay(BaseModel):
    date: date
    posts: int = Field(ge=0)
    comments: int = Field(ge=0)
    count: int = Field(ge=0)


class PublicActivity(BaseModel):
    timezone: Literal["Asia/Ho_Chi_Minh"] = TIMEZONE
    start_date: date
    end_date: date
    days: list[ActivityDay] = Field(min_length=371, max_length=371)
    total: int = Field(ge=0)


def activity_window(now):
    today = now.astimezone(ZoneInfo(TIMEZONE)).date()
    return today - timedelta(days=today.weekday(), weeks=52), today


@router.get("/{username}/activity", response_model=PublicActivity, operation_id="getPublicUserActivity",
            responses={status: {"model": ErrorResponse} for status in (404, 422, 429, 500)})
def public_user_activity(request: Request, username: str = Path(min_length=3, max_length=32, pattern=r"^[a-z0-9_]+$")):
    now = request.app.state.auth.now()
    start, today = activity_window(now)
    since = datetime.combine(start, time.min, tzinfo=ZoneInfo(TIMEZONE))
    with request.app.state.auth_session_factory() as db:
        owner = db.scalar(select(User.id).join(Profile, Profile.user_id == User.id).where(
            User.username == username, User.status == "active"))
        if owner is None:
            raise AuthError(404, "NOT_FOUND", "Profile not found.")
        post_day = func.timezone(TIMEZONE, Post.created_at).cast(Date)
        posts = dict(db.execute(public_posts().with_only_columns(post_day, func.count()).where(
            Post.author_id == owner, Post.created_at >= since, Post.created_at <= now).group_by(post_day)).all())
        comment_day = func.timezone(TIMEZONE, Comment.created_at).cast(Date)
        comments = dict(db.execute(select(comment_day, func.count()).where(
            Comment.author_id == owner, Comment.status == "visible", Comment.deleted_at.is_(None),
            Comment.created_at >= since, Comment.created_at <= now,
            Comment.post_id.in_(public_posts().with_only_columns(Post.id))).group_by(comment_day)).all())
    days = []
    for offset in range(371):
        day = start + timedelta(days=offset)
        post_count, comment_count = posts.get(day, 0), comments.get(day, 0)
        days.append(ActivityDay(date=day, posts=post_count, comments=comment_count, count=post_count + comment_count))
    return PublicActivity(start_date=start, end_date=today, days=days, total=sum(day.count for day in days))

"""P1 interactions only: stable per-user rows, no reward issuance."""
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from sqlalchemy import delete
from sqlalchemy.dialects.postgresql import insert

from app.auth import CSRF_HEADER, ERRORS
from app.auth_schemas import ErrorResponse
from app.comments import lock_public_post
from app.models import PostBookmark, PostReaction
from app.permissions import require_account_csrf

router = APIRouter(prefix="/api/v1/posts", tags=["Aura"])
ERRORS = ERRORS | {404: {"model": ErrorResponse}, 409: {"model": ErrorResponse}}


class ReactionInput(BaseModel):
    reaction_type: Literal["like", "laugh", "fire"]


class ReactionResult(ReactionInput):
    post_id: UUID


@router.put("/{post_id}/reactions", response_model=ReactionResult, operation_id="setReaction",
            responses=ERRORS, openapi_extra=CSRF_HEADER)
def set_reaction(post_id: UUID, payload: ReactionInput, request: Request, account=Depends(require_account_csrf)):
    lock_public_post(account.db, post_id)
    now = request.app.state.auth.now()
    statement = insert(PostReaction).values(post_id=post_id, user_id=account.user.id,
        reaction_type=payload.reaction_type, created_at=now, updated_at=now)
    account.db.execute(statement.on_conflict_do_update(index_elements=["post_id", "user_id"],
        set_={"reaction_type": payload.reaction_type, "updated_at": now},
        where=PostReaction.reaction_type != payload.reaction_type))
    return ReactionResult(post_id=post_id, reaction_type=payload.reaction_type)


@router.delete("/{post_id}/reactions", status_code=204, operation_id="removeReaction",
               responses=ERRORS, openapi_extra=CSRF_HEADER)
def remove_reaction(post_id: UUID, account=Depends(require_account_csrf)):
    lock_public_post(account.db, post_id)
    account.db.execute(delete(PostReaction).where(PostReaction.post_id == post_id, PostReaction.user_id == account.user.id))


@router.put("/{post_id}/bookmark", status_code=204, operation_id="savePost",
            responses=ERRORS, openapi_extra=CSRF_HEADER)
def save_post(post_id: UUID, request: Request, account=Depends(require_account_csrf)):
    lock_public_post(account.db, post_id)
    account.db.execute(insert(PostBookmark).values(post_id=post_id, user_id=account.user.id,
        created_at=request.app.state.auth.now()).on_conflict_do_nothing(index_elements=["post_id", "user_id"]))


@router.delete("/{post_id}/bookmark", status_code=204, operation_id="unsavePost",
               responses=ERRORS, openapi_extra=CSRF_HEADER)
def unsave_post(post_id: UUID, account=Depends(require_account_csrf)):
    lock_public_post(account.db, post_id)
    account.db.execute(delete(PostBookmark).where(PostBookmark.post_id == post_id, PostBookmark.user_id == account.user.id))

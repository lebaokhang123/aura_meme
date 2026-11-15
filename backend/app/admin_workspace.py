"""Read-only Admin lists; no catalog publishing or new permission system."""
from typing import Literal
from uuid import UUID
from fastapi import APIRouter, Depends, Query, Response
from pydantic import BaseModel
from sqlalchemy import case, select
from app.auth import ERRORS
from app.auth_schemas import ErrorResponse
from app.blog import page_rows
from app.blog_schemas import Pagination
from app.comments import CommentResponse, comment_dto
from app.models import AssetItem, Comment, MediaUpload, Post, Profile, User
from app.media import image_response
from app.permissions import require_role
from app.security import AuthError

router=APIRouter(prefix='/api/v1/admin',tags=['Admin'])
ReviewStatus=Literal['pending','approved','rejected','unknown']
AssetKind=Literal['avatar','frame','icon','effect','background']

class AdminComment(CommentResponse):
    status:Literal['visible','hidden','deleted']

class AdminCommentPage(BaseModel):
    items:list[AdminComment]
    pagination:Pagination

class AdminAsset(BaseModel):
    id:UUID
    slug:str
    kind:AssetKind
    rarity:Literal['D','C','B','A','S']
    active:bool
    review_status:ReviewStatus

class AdminAssetPage(BaseModel):
    items:list[AdminAsset]
    pagination:Pagination

@router.get('/comments',response_model=AdminCommentPage,operation_id='adminListComments',responses={s:ERRORS[s] for s in (401,403,422,429,500)})
def comments(page:int=Query(1,ge=1),page_size:int=Query(20,ge=1,le=100),
             search:str|None=Query(None,max_length=100),status:Literal['visible','hidden','deleted']|None=None,
             post_id:UUID|None=None,account=Depends(require_role('ADMIN'))):
    if search is not None and '\x00' in search:raise AuthError(422,'VALIDATION_ERROR','Invalid query text.')
    statement=select(Comment,User,Profile).join(User,User.id==Comment.author_id).join(Profile,Profile.user_id==User.id)
    if search is not None:statement=statement.where(Comment.body.icontains(search,autoescape=True))
    if status is not None:statement=statement.where(Comment.status==status)
    if post_id is not None:statement=statement.where(Comment.post_id==post_id)
    rows,pagination=page_rows(account.db,statement.order_by(Comment.created_at.desc(),Comment.id.desc()),page,page_size)
    return AdminCommentPage(items=[AdminComment(**comment_dto(*row).model_dump(),status=row[0].status) for row in rows],pagination=pagination)

@router.get('/assets',response_model=AdminAssetPage,operation_id='adminListAssets',responses={s:ERRORS[s] for s in (401,403,422,429,500)})
def assets(page:int=Query(1,ge=1),page_size:int=Query(20,ge=1,le=100),
           search:str|None=Query(None,max_length=100),kind:AssetKind|None=None,
           active:bool|None=None,review_status:ReviewStatus|None=None,account=Depends(require_role('ADMIN'))):
    if search is not None and '\x00' in search:raise AuthError(422,'VALIDATION_ERROR','Invalid query text.')
    saved_review=AssetItem.source_rights['review_status'].astext
    reviewed=case((saved_review.in_(['pending','approved','rejected']),saved_review),else_='unknown')
    # Select only status metadata; private media keys/provenance never enter this DTO.
    statement=select(AssetItem.id,AssetItem.slug,AssetItem.kind,AssetItem.rarity,AssetItem.active,reviewed.label('review_status'))
    if search is not None:statement=statement.where(AssetItem.slug.icontains(search,autoescape=True))
    if kind is not None:statement=statement.where(AssetItem.kind==kind)
    if active is not None:statement=statement.where(AssetItem.active==active)
    if review_status is not None:statement=statement.where(reviewed==review_status)
    rows,pagination=page_rows(account.db,statement.order_by(AssetItem.slug,AssetItem.id),page,page_size)
    return AdminAssetPage(items=[AdminAsset(**row._mapping) for row in rows],pagination=pagination)

@router.get('/posts/{post_id}/media',response_class=Response,operation_id='adminReadPostImage',responses={200:{'content':{mime:{'schema':{'type':'string','format':'binary'}} for mime in ('image/png','image/gif')}},**{s:ERRORS[s] for s in (401,403,422,429,500)},404:{'model':ErrorResponse}})
def post_image(post_id:UUID,still:bool=False,account=Depends(require_role('ADMIN'))):
    post=account.db.scalar(select(Post).where(Post.id==post_id).with_for_update(read=True))
    if post is None or post.status=='deleted' or post.media_id is None:
        raise AuthError(404,'NOT_FOUND','Image not available.')
    # Bind this privileged read to a post; unrelated private uploads remain inaccessible.
    media=account.db.scalar(select(MediaUpload).where(MediaUpload.id==post.media_id,MediaUpload.owner_id==post.author_id,MediaUpload.status=='ready').with_for_update(read=True))
    if media is None:raise AuthError(404,'NOT_FOUND','Image not available.')
    return image_response(media,still=still)

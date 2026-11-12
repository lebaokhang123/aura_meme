"""Private author reads; public visibility and media delivery remain unchanged."""
from typing import Literal
from uuid import UUID
from fastapi import APIRouter, Depends, Query
from sqlalchemy import or_, select
from app.auth import ERRORS
from app.auth_schemas import ErrorResponse
from app.blog import page_rows,post_dto
from app.blog_schemas import Pagination,PostResponse
from app.models import Category,Post,Profile,User
from app.permissions import require_authenticated_user
from app.security import AuthError
from pydantic import BaseModel

router=APIRouter(prefix='/api/v1/users/me/posts',tags=['Blog'])


class OwnPost(PostResponse):
    media_id:UUID|None


class OwnPostPage(BaseModel):
    items:list[OwnPost]
    pagination:Pagination


def own_query(actor):
    return select(Post,User,Profile,Category).join(User,User.id==Post.author_id).join(Profile,Profile.user_id==User.id).join(Category,Category.id==Post.category_id).where(Post.author_id==actor,Post.status!='deleted')


def own_dto(post,user,profile,category):
    return OwnPost(**post_dto(post,user,profile,category).model_dump(),media_id=post.media_id)


@router.get('',response_model=OwnPostPage,operation_id='listOwnPosts',responses={code:ERRORS[code] for code in (401,403,422,429,500)})
def list_own_posts(page:int=Query(1,ge=1),page_size:int=Query(20,ge=1,le=100),
    status:Literal['draft','published','hidden']|None=None,search:str|None=Query(None,max_length=100),
    category:str|None=None,sort:Literal['created_desc','created_asc','title_asc']='created_desc',
    account=Depends(require_authenticated_user,scope='function')):
    if any(value is not None and '\x00' in value for value in (search,category)):
        raise AuthError(422,'VALIDATION_ERROR','Invalid query text.')
    query=own_query(account.user.id)
    if status is not None:query=query.where(Post.status==status)
    if search is not None:query=query.where(or_(Post.title.icontains(search,autoescape=True),Post.content.icontains(search,autoescape=True)))
    if category is not None:query=query.where(Category.slug==category)
    ordering={'created_desc':(Post.created_at.desc(),Post.id.desc()),'created_asc':(Post.created_at,Post.id),'title_asc':(Post.title,Post.id)}
    rows,pagination=page_rows(account.db,query.order_by(*ordering[sort]),page,page_size)
    return OwnPostPage(items=[own_dto(*row) for row in rows],pagination=pagination)


@router.get('/{post_id}',response_model=OwnPost,operation_id='getOwnPost',responses={code:ERRORS[code] for code in (401,403,422,429,500)}|{404:{'model':ErrorResponse}})
def get_own_post(post_id:UUID,account=Depends(require_authenticated_user,scope='function')):
    row=account.db.execute(own_query(account.user.id).where(Post.id==post_id)).one_or_none()
    if row is None:raise AuthError(404,'NOT_FOUND','Post not found.')
    return own_dto(*row)

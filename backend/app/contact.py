"""Private contact inbox: Guest pre-session or User session CSRF, no email sending."""
from contextlib import contextmanager
from datetime import datetime
from typing import Literal
from uuid import UUID, uuid4
from fastapi import APIRouter, Depends, Query, Request, Response
from pydantic import BaseModel, EmailStr, Field, field_validator
from sqlalchemy import select

from app.admin_users import require_admin_mutation
from app.auth import CSRF_HEADER, ERRORS, guest_guard
from app.auth_schemas import ErrorResponse
from app.blog import page_rows
from app.blog_schemas import Pagination, StrictInput
from app.models import AdminAuditLog, ContactMessage
from app.permissions import require_account_csrf, require_authenticated_user, require_role
from app.security import AuthError

router=APIRouter(prefix="/api/v1",tags=["Contact"])


class ContactInput(StrictInput):
    name:str=Field(min_length=1,max_length=100)
    email:EmailStr
    subject:str=Field(min_length=1,max_length=160)
    body:str=Field(min_length=1,max_length=4000)

    @field_validator("name","subject","body")
    @classmethod
    def nonblank(cls,value):
        if not value.strip():raise ValueError("Contact fields must not be blank.")
        return value


class ContactCreated(BaseModel):
    id:UUID
    status:Literal["new"]


class ContactResponse(BaseModel):
    id:UUID
    name:str
    email:EmailStr
    subject:str
    body:str
    status:Literal["new","in_review","resolved"]
    created_at:datetime


class ContactPage(BaseModel):
    items:list[ContactResponse]
    pagination:Pagination


class AdminContactPatch(StrictInput):
    status:Literal["new","in_review","resolved"]


def contact_writer(request:Request,response:Response):
    raw=request.cookies.get("am_session")
    if raw:
        try:
            with contextmanager(require_authenticated_user)(request,response,raw) as account:
                require_account_csrf(request,account)
                yield account.db,account.user.id
        except AuthError as error:
            if error.status==401:
                raise AuthError(403,"CSRF_INVALID","Contact session binding expired; refresh CSRF.") from None
            raise
    else:
        guest_guard(request)
        with request.app.state.auth_session_factory() as db,db.begin():
            yield db,None


@router.post("/contact",status_code=201,response_model=ContactCreated,operation_id="sendContact",
    responses={code:ERRORS[code] for code in (403,409,422,429,500)},openapi_extra=CSRF_HEADER)
def send_contact(payload:ContactInput,request:Request,writer=Depends(contact_writer,scope="function")):
    db,user_id=writer
    now=request.app.state.auth.now()
    row=ContactMessage(id=uuid4(),user_id=user_id,**payload.model_dump(),status="new",created_at=now,updated_at=now)
    db.add(row);db.flush()
    return ContactCreated(id=row.id,status="new")


@router.get("/admin/contacts",response_model=ContactPage,operation_id="adminListContacts",tags=["Admin"],
    responses={code:ERRORS[code] for code in (401,403,422,429,500)})
def list_contacts(page:int=Query(1,ge=1),page_size:int=Query(20,ge=1,le=100),status:str|None=None,
                  account=Depends(require_role("ADMIN"))):
    if status is not None and "\x00" in status:
        raise AuthError(422,"VALIDATION_ERROR","Invalid query text.")
    statement=select(ContactMessage)
    if status is not None:statement=statement.where(ContactMessage.status==status)
    rows,pagination=page_rows(account.db,statement.order_by(ContactMessage.created_at.desc(),ContactMessage.id.desc()),page,page_size)
    return ContactPage(items=[ContactResponse.model_validate(row[0],from_attributes=True) for row in rows],pagination=pagination)


@router.patch("/admin/contacts/{contact_id}",response_model=ContactResponse,operation_id="adminSetContactStatus",tags=["Admin"],
    responses=ERRORS|{404:{"model":ErrorResponse}},openapi_extra=CSRF_HEADER)
def set_contact_status(contact_id:UUID,payload:AdminContactPatch,request:Request,
                       account=Depends(require_admin_mutation,scope="function")):
    row=account.db.scalar(select(ContactMessage).where(ContactMessage.id==contact_id).with_for_update().execution_options(populate_existing=True))
    if row is None:raise AuthError(404,"NOT_FOUND","Contact not found.")
    before={"status":row.status}
    row.status,row.updated_at=payload.status,request.app.state.auth.now()
    account.db.add(AdminAuditLog(id=uuid4(),actor_id=account.user.id,action="contact.update",target_type="contact",
        target_id=str(row.id),before_json=before,after_json={"status":row.status},created_at=row.updated_at))
    account.db.flush()
    return ContactResponse.model_validate(row,from_attributes=True)

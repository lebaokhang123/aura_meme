"""Authenticated private contact inbox with session CSRF; no email sending."""
from datetime import datetime
from typing import Literal
from uuid import UUID, uuid4
from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, EmailStr, Field, field_validator
from sqlalchemy import or_, select

from app.admin_users import require_admin_mutation
from app.auth import CSRF_HEADER, ERRORS
from app.auth_schemas import ErrorResponse
from app.blog import page_rows
from app.blog_schemas import Pagination, StrictInput
from app.models import AdminAuditLog, ContactMessage
from app.permissions import require_account_csrf, require_role
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


@router.post("/contact",status_code=201,response_model=ContactCreated,operation_id="sendContact",
    responses={code:ERRORS[code] for code in (401,403,409,422,429,500)},openapi_extra=CSRF_HEADER)
def send_contact(payload:ContactInput,request:Request,account=Depends(require_account_csrf)):
    db,user_id=account.db,account.user.id
    now=request.app.state.auth.now()
    row=ContactMessage(id=uuid4(),user_id=user_id,**payload.model_dump(),status="new",created_at=now,updated_at=now)
    db.add(row);db.flush()
    return ContactCreated(id=row.id,status="new")


@router.get("/admin/contacts",response_model=ContactPage,operation_id="adminListContacts",tags=["Admin"],
    responses={code:ERRORS[code] for code in (401,403,422,429,500)})
def list_contacts(page:int=Query(1,ge=1),page_size:int=Query(20,ge=1,le=100),status:str|None=None,
                  search:str|None=Query(None,max_length=100),sort:Literal["created_desc","created_asc","subject_asc"]="created_desc",
                  account=Depends(require_role("ADMIN"))):
    if any(value is not None and "\x00" in value for value in (search,status)):
        raise AuthError(422,"VALIDATION_ERROR","Invalid query text.")
    statement=select(ContactMessage)
    if status is not None:statement=statement.where(ContactMessage.status==status)
    if search is not None:statement=statement.where(or_(*(column.icontains(search,autoescape=True) for column in (ContactMessage.name,ContactMessage.email,ContactMessage.subject,ContactMessage.body))))
    ordering={"created_desc":(ContactMessage.created_at.desc(),ContactMessage.id.desc()),"created_asc":(ContactMessage.created_at,ContactMessage.id),"subject_asc":(ContactMessage.subject,ContactMessage.id)}
    rows,pagination=page_rows(account.db,statement.order_by(*ordering[sort]),page,page_size)
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

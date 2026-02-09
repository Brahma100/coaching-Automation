from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db import get_db
from app.services.allowlist_admin_service import (
    activate_allowed_user_admin,
    deactivate_allowed_user_admin,
    list_allowed_users_admin,
    require_admin_session,
    invite_allowed_user,
)


router = APIRouter(prefix='/api/admin/allowed-users', tags=['Admin Allowlist API'])


class AllowedUserResponse(BaseModel):
    id: int
    phone: str
    role: str
    status: str
    created_at: datetime


class InviteAllowedUserPayload(BaseModel):
    phone: str
    role: str


class PhonePayload(BaseModel):
    phone: str


def _resolve_token(request: Request) -> str | None:
    token = request.cookies.get('auth_session')
    if token:
        return token

    authorization = request.headers.get('authorization', '')
    if authorization.lower().startswith('bearer '):
        return authorization[7:].strip()
    return None


def _require_admin(request: Request, db: Session = Depends(get_db)) -> dict:
    token = _resolve_token(request)
    try:
        return require_admin_session(db, token)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc) or 'Forbidden') from exc


def _serialize(row) -> AllowedUserResponse:
    return AllowedUserResponse(
        id=row.id,
        phone=row.phone,
        role=row.role,
        status=row.status,
        created_at=row.created_at,
    )


@router.get('', response_model=list[AllowedUserResponse])
def admin_list_allowed_users(
    _: dict = Depends(_require_admin),
    db: Session = Depends(get_db),
):
    rows = list_allowed_users_admin(db)
    return [_serialize(row) for row in rows]


@router.post('/invite', response_model=AllowedUserResponse)
def admin_invite_allowed_user(
    payload: InviteAllowedUserPayload,
    _: dict = Depends(_require_admin),
    db: Session = Depends(get_db),
):
    try:
        row = invite_allowed_user(db, payload.phone, payload.role)
        return _serialize(row)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post('/activate', response_model=AllowedUserResponse)
def admin_activate_allowed_user(
    payload: PhonePayload,
    _: dict = Depends(_require_admin),
    db: Session = Depends(get_db),
):
    try:
        row = activate_allowed_user_admin(db, payload.phone)
        return _serialize(row)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post('/deactivate', response_model=AllowedUserResponse)
def admin_deactivate_allowed_user(
    payload: PhonePayload,
    _: dict = Depends(_require_admin),
    db: Session = Depends(get_db),
):
    try:
        row = deactivate_allowed_user_admin(db, payload.phone)
        return _serialize(row)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

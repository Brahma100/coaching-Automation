from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Role
from app.services.auth_service import add_allowed_user, deactivate_allowed_user, list_allowed_users, validate_session_token


router = APIRouter(prefix='/admin/allowlist', tags=['Admin Allowlist'])


class AllowlistAddPayload(BaseModel):
    phone: str
    role: str


class AllowlistDeactivatePayload(BaseModel):
    phone: str


class AllowedUserResponse(BaseModel):
    id: int
    phone: str
    role: str
    status: str
    created_at: datetime


def _resolve_token(request: Request) -> str | None:
    token = request.cookies.get('auth_session')
    if token:
        return token

    authorization = request.headers.get('authorization', '')
    if authorization.lower().startswith('bearer '):
        return authorization[7:].strip()
    return None


def _require_admin(request: Request) -> dict:
    token = _resolve_token(request)
    session = validate_session_token(token)
    if not session:
        raise HTTPException(status_code=401, detail='Unauthorized')
    if session.get('role') != Role.ADMIN.value:
        raise HTTPException(status_code=403, detail='Admin access required')
    return session


def _to_response(row) -> AllowedUserResponse:
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
    rows = list_allowed_users(db)
    return [_to_response(row) for row in rows]


@router.post('', response_model=AllowedUserResponse)
def admin_add_allowed_user(
    payload: AllowlistAddPayload,
    _: dict = Depends(_require_admin),
    db: Session = Depends(get_db),
):
    try:
        row = add_allowed_user(db, payload.phone, payload.role)
        return _to_response(row)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post('/deactivate', response_model=AllowedUserResponse)
def admin_deactivate_allowed_user(
    payload: AllowlistDeactivatePayload,
    _: dict = Depends(_require_admin),
    db: Session = Depends(get_db),
):
    try:
        row = deactivate_allowed_user(db, payload.phone)
        return _to_response(row)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import AuthUser, Role
from app.services.auth_service import validate_session_token

router = APIRouter(prefix='/api/teacher/profile', tags=['Teacher Profile'])


class TeacherProfileUpdate(BaseModel):
    notification_delete_minutes: int = Field(ge=1, le=240)


def _require_teacher(request: Request) -> dict:
    token = request.cookies.get('auth_session')
    session = validate_session_token(token)
    if not session:
        raise HTTPException(status_code=403, detail='Unauthorized')
    role = (session.get('role') or '').lower()
    if role not in (Role.TEACHER.value, Role.ADMIN.value):
        raise HTTPException(status_code=403, detail='Unauthorized')
    return session


@router.get('')
def get_profile(request: Request, _: dict = Depends(_require_teacher), db: Session = Depends(get_db)):
    session = validate_session_token(request.cookies.get('auth_session'))
    if not session:
        raise HTTPException(status_code=403, detail='Unauthorized')
    auth_user = db.query(AuthUser).filter(AuthUser.id == session['user_id']).first()
    if not auth_user:
        raise HTTPException(status_code=404, detail='User not found')
    return {
        'id': auth_user.id,
        'phone': auth_user.phone,
        'role': auth_user.role,
        'notification_delete_minutes': auth_user.notification_delete_minutes or 15,
    }


@router.put('')
def update_profile(
    payload: TeacherProfileUpdate,
    request: Request,
    _: dict = Depends(_require_teacher),
    db: Session = Depends(get_db),
):
    session = validate_session_token(request.cookies.get('auth_session'))
    if not session:
        raise HTTPException(status_code=403, detail='Unauthorized')
    auth_user = db.query(AuthUser).filter(AuthUser.id == session['user_id']).first()
    if not auth_user:
        raise HTTPException(status_code=404, detail='User not found')
    auth_user.notification_delete_minutes = payload.notification_delete_minutes
    db.commit()
    db.refresh(auth_user)
    return {
        'id': auth_user.id,
        'notification_delete_minutes': auth_user.notification_delete_minutes,
    }
